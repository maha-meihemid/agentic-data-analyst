from pathlib import Path

import duckdb
import pytest


@pytest.fixture()
def sample_db(tmp_path: Path) -> Path:
    path = tmp_path / "sample.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("""CREATE TABLE trips AS SELECT * FROM (VALUES
    (TIMESTAMP '2024-01-01 08:00:00', TIMESTAMP '2024-01-01 08:10:00', 1.0, 1, 10.0, 2.0, 12.0),
    (TIMESTAMP '2024-01-02 09:00:00', TIMESTAMP '2024-01-02 09:20:00', 2.0, 2, 20.0, 0.0, 20.0)
    ) t(tpep_pickup_datetime, tpep_dropoff_datetime, trip_distance, payment_type,
    fare_amount, tip_amount, total_amount)""")
    connection.execute("CREATE TABLE taxi_zones(LocationID INTEGER, Borough VARCHAR, Zone VARCHAR)")
    connection.execute(
        "CREATE VIEW trips_enriched AS SELECT *, "
        "'Manhattan' AS pickup_borough, 'Test' AS pickup_zone FROM trips"
    )
    connection.close()
    return path
