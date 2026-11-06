import pytest

from data_analyst.sql import UnsafeQuery, execute_readonly, validate_sql


def test_select_executes_with_row_cap(sample_db):
    assert len(execute_readonly("SELECT * FROM trips", sample_db, max_rows=1).dataframe) == 1


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM trips",
        "SELECT * FROM read_parquet('x')",
        "SELECT * FROM trips; DROP TABLE trips",
        "ATTACH 'x' AS other",
        "COPY trips TO 'x'",
        "SELECT * FROM secrets",
    ],
)
def test_unsafe_sql_is_rejected(query):
    with pytest.raises(UnsafeQuery):
        validate_sql(query)


def test_cte_is_allowed():
    assert validate_sql("WITH totals AS (SELECT count(*) n FROM trips) SELECT n FROM totals")
