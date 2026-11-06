"""A compact LangGraph workflow that turns a question into safe SQL."""

import json
from collections.abc import Callable
from time import perf_counter
from typing import TypedDict
from uuid import uuid4

from google import genai
from langgraph.graph import END, START, StateGraph

from data_analyst.config import settings
from data_analyst.sql import UnsafeQuery, describe_dataset, execute_readonly, validate_sql
from data_analyst.telemetry import ERRORS, LLM_SECONDS, REQUESTS, TOKENS, log_event


class AnalystState(TypedDict, total=False):
    request_id: str
    question: str
    schema: dict
    sql: str
    answer: str
    rows: list[dict]
    columns: list[str]
    error: str
    correction_count: int
    latency_ms: float
    tokens: dict


def _call_model(prompt: str) -> tuple[str, dict]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=settings.gemini_api_key)
    started = perf_counter()
    response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
    LLM_SECONDS.observe(perf_counter() - started)
    usage = getattr(response, "usage_metadata", None)
    tokens = {
        "input": getattr(usage, "prompt_token_count", 0) or 0,
        "output": getattr(usage, "candidates_token_count", 0) or 0,
    }
    for kind, count in tokens.items():
        TOKENS.labels(kind).inc(count)
    return response.text or "", tokens


def build_graph(model_call: Callable[[str], tuple[str, dict]] = _call_model):
    def understand(state: AnalystState) -> AnalystState:
        question = state["question"].strip()
        if not question:
            return {"error": "Please enter a question."}
        return {"request_id": state.get("request_id", str(uuid4())), "schema": describe_dataset()}

    def generate(state: AnalystState) -> AnalystState:
        prompt = f"""Return only one DuckDB SELECT query. No markdown. Use only trips_enriched or
taxi_zones. Dataset schema: {json.dumps(state["schema"], default=str)}
Question: {state["question"]}
Always aggregate when sensible and keep output under 500 rows. Never use file functions."""
        text, tokens = model_call(prompt)
        return {
            "sql": text.strip().removeprefix("```sql").removesuffix("```").strip(),
            "tokens": tokens,
        }

    def validate(state: AnalystState) -> AnalystState:
        try:
            return {"sql": validate_sql(state["sql"]), "error": ""}
        except UnsafeQuery as error:
            return {"error": str(error)}

    def execute(state: AnalystState) -> AnalystState:
        try:
            result = execute_readonly(state["sql"])
            return {
                "rows": result.dataframe.to_dict("records"),
                "columns": list(result.dataframe.columns),
                "latency_ms": result.latency_ms,
                "error": "",
            }
        except Exception as error:
            return {"error": f"Query failed: {error}"}

    def summarize(state: AnalystState) -> AnalystState:
        prompt = f"""Answer the question in 2 or 3 plain English sentences using only these rows.
State the scope and do not invent facts. Question: {state["question"]}
Rows: {json.dumps(state.get("rows", [])[:50], default=str)}"""
        answer, more_tokens = model_call(prompt)
        tokens = state.get("tokens", {})
        return {
            "answer": answer.strip(),
            "tokens": {k: tokens.get(k, 0) + more_tokens.get(k, 0) for k in {"input", "output"}},
        }

    def after_understand(state: AnalystState) -> str:
        return END if state.get("error") else "generate_sql"

    def after_validation(state: AnalystState) -> str:
        return END if state.get("error") else "execute_sql"

    def after_execution(state: AnalystState) -> str:
        return END if state.get("error") else "summarize"

    graph = StateGraph(AnalystState)
    graph.add_node("understand_question", understand)
    graph.add_node("generate_sql", generate)
    graph.add_node("validate_sql", validate)
    graph.add_node("execute_sql", execute)
    graph.add_node("summarize", summarize)
    graph.add_edge(START, "understand_question")
    graph.add_conditional_edges("understand_question", after_understand)
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges("validate_sql", after_validation)
    graph.add_conditional_edges("execute_sql", after_execution)
    graph.add_edge("summarize", END)
    return graph.compile()


def ask(question: str) -> AnalystState:
    started = perf_counter()
    request_id = str(uuid4())
    try:
        result = build_graph().invoke({"question": question, "request_id": request_id})
        outcome = "error" if result.get("error") else "success"
        REQUESTS.labels(outcome).inc()
        log_event(
            request_id,
            "workflow",
            outcome,
            started,
            error_type="" if outcome == "success" else "workflow",
        )
        return result
    except Exception as error:
        ERRORS.labels("workflow", type(error).__name__).inc()
        REQUESTS.labels("error").inc()
        log_event(request_id, "workflow", "error", started, error_type=type(error).__name__)
        return {"request_id": request_id, "question": question, "error": str(error)}
