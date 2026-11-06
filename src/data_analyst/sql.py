"""Parse, validate, and execute a deliberately small read-only SQL subset."""

from dataclasses import dataclass
from time import perf_counter

import duckdb
import pandas as pd
from sqlglot import exp, parse

from data_analyst.config import settings

ALLOWED_TABLES = {"trips", "taxi_zones", "trips_enriched"}
BLOCKED_NODES = (
    exp.Command,
    exp.Copy,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Update,
    exp.Create,
    exp.Alter,
    exp.Merge,
    exp.Attach,
    exp.Pragma,
    exp.Transaction,
)
BLOCKED_FUNCTIONS = {
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_parquet",
    "glob",
    "httpfs",
    "parquet_scan",
    "sqlite_scan",
    "postgres_scan",
}


class UnsafeQuery(ValueError):
    pass


@dataclass
class QueryResult:
    dataframe: pd.DataFrame
    latency_ms: float
    sql: str


def validate_sql(sql: str) -> str:
    try:
        statements = parse(sql, read="duckdb")
    except Exception as error:
        raise UnsafeQuery(f"SQL could not be parsed: {error}") from error
    if len(statements) != 1:
        raise UnsafeQuery("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise UnsafeQuery("Only SELECT queries, including WITH ... SELECT, are allowed")
    if any(tree.find(node) for node in BLOCKED_NODES):
        raise UnsafeQuery("The query contains a write or administrative operation")
    tables = {table.name.lower() for table in tree.find_all(exp.Table)}
    ctes = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
    unknown = tables - ALLOWED_TABLES - ctes
    if unknown:
        raise UnsafeQuery(f"Unknown table(s): {', '.join(sorted(unknown))}")
    functions = {function.sql_name().lower() for function in tree.find_all(exp.Func)}
    blocked = functions & BLOCKED_FUNCTIONS
    if blocked:
        raise UnsafeQuery(f"Unsafe function(s): {', '.join(sorted(blocked))}")
    return tree.sql(dialect="duckdb")


def execute_readonly(sql: str, db_path=None, max_rows: int | None = None) -> QueryResult:
    safe_sql = validate_sql(sql)
    limit = max_rows or settings.max_result_rows
    wrapped = f"SELECT * FROM ({safe_sql}) AS safe_result LIMIT {int(limit)}"
    started = perf_counter()
    connection = duckdb.connect(str(db_path or settings.db_path), read_only=True)
    try:
        dataframe = connection.execute(wrapped).fetchdf()
    finally:
        connection.close()
    return QueryResult(dataframe, (perf_counter() - started) * 1000, safe_sql)


def describe_dataset(db_path=None) -> dict:
    connection = duckdb.connect(str(db_path or settings.db_path), read_only=True)
    try:
        row = connection.execute(
            "SELECT count(*), min(tpep_pickup_datetime), max(tpep_pickup_datetime) FROM trips"
        ).fetchone()
        columns = connection.execute("DESCRIBE trips_enriched").fetchdf()[
            ["column_name", "column_type"]
        ]
    finally:
        connection.close()
    return {
        "row_count": row[0],
        "start": row[1].isoformat() if row[1] else None,
        "end": row[2].isoformat() if row[2] else None,
        "columns": columns.to_dict("records"),
    }
