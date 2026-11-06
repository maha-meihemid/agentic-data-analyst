"""Read-only MCP access to the same validated data functions as the app."""

from mcp.server.fastmcp import FastMCP

from data_analyst.sql import describe_dataset, execute_readonly

mcp = FastMCP("NYC Taxi Analyst")


@mcp.tool()
def dataset_description() -> dict:
    """Return row count, coverage, and columns for the loaded sample."""
    return describe_dataset()


@mcp.tool()
def run_readonly_query(sql: str) -> dict:
    """Run one validated SELECT query and return no more than the configured row cap."""
    result = execute_readonly(sql)
    return {
        "columns": list(result.dataframe.columns),
        "rows": result.dataframe.to_dict("records"),
        "latency_ms": round(result.latency_ms, 2),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
