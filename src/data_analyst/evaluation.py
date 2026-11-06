"""Reproducible result-equivalence evaluation for the analyst."""

import argparse
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path

from data_analyst.agent import ask
from data_analyst.sql import execute_readonly


def equivalent_rows(actual: list[dict], expected: list[dict], tolerance: float = 1e-6) -> bool:
    if len(actual) != len(expected) or (actual and actual[0].keys() != expected[0].keys()):
        return False
    for actual_row, expected_row in zip(actual, expected, strict=True):
        for key in actual_row:
            left, right = actual_row[key], expected_row[key]
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if not math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance):
                    return False
            elif str(left) != str(right):
                return False
    return True


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def run_evaluation(path: Path) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    results, latencies = [], []
    for case in cases:
        response = ask(case["question"])
        latency = response.get("latency_ms", 0.0)
        latencies.append(latency)
        if case["kind"] == "refusal":
            passed = bool(response.get("error"))
        else:
            expected = execute_readonly(case["reference_sql"]).dataframe.to_dict("records")
            passed = not response.get("error") and equivalent_rows(
                response.get("rows", []), expected
            )
        results.append({"id": case["id"], "passed": passed, "error": response.get("error", "")})
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "cases": results,
        "execution_accuracy": statistics.fmean(item["passed"] for item in results),
        "p50_latency_ms": percentile(latencies, 0.5),
        "p95_latency_ms": percentile(latencies, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.json"))
    parser.add_argument("--output", type=Path, default=Path("eval/results/latest.json"))
    args = parser.parse_args()
    result = run_evaluation(args.questions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
