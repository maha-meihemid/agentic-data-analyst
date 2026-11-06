"""Standard logging and local Prometheus measurements."""

import json
import logging
from time import perf_counter

from prometheus_client import Counter, Histogram, start_http_server

REQUESTS = Counter("analyst_requests_total", "Analyst requests", ["outcome"])
ERRORS = Counter("analyst_errors_total", "Analyst errors", ["stage", "type"])
QUERY_SECONDS = Histogram("analyst_query_seconds", "DuckDB query duration")
LLM_SECONDS = Histogram("analyst_llm_seconds", "Gemini call duration")
TOKENS = Counter("analyst_tokens_total", "Reported model token usage", ["kind"])


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(request_id: str, stage: str, outcome: str, started: float, **fields) -> None:
    payload = {
        "request_id": request_id,
        "stage": stage,
        "outcome": outcome,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        **fields,
    }
    logging.getLogger("data_analyst").info(json.dumps(payload, default=str))


def start_metrics(port: int) -> None:
    start_http_server(port, addr="127.0.0.1")
