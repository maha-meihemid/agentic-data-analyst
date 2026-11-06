"""Download and load the official NYC TLC sample."""

import argparse
import csv
import urllib.request
from pathlib import Path

import duckdb

from data_analyst.config import settings

DATA_MONTH = "2024-01"
TRIP_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
TRIP_FILE = "yellow_tripdata_2024-01.parquet"
ZONE_FILE = "taxi_zone_lookup.csv"
REQUIRED_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount",
}


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_parquet(path: Path) -> int:
    connection = duckdb.connect(":memory:")
    columns = {
        row[0]
        for row in connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
        ).fetchall()
    }
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"TLC file is missing required columns: {sorted(missing)}")
    return connection.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]


def validate_zones(path: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        headers = set(next(csv.DictReader(handle)).keys())
    required = {"LocationID", "Borough", "Zone", "service_zone"}
    if not required <= headers:
        raise ValueError(f"Zone file is missing columns: {sorted(required - headers)}")


def build_database(trip_path: Path, zone_path: Path, db_path: Path, row_limit: int) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(db_path))
    connection.execute("DROP VIEW IF EXISTS trips_enriched")
    connection.execute("DROP TABLE IF EXISTS trips")
    connection.execute("DROP TABLE IF EXISTS taxi_zones")
    connection.execute(
        """CREATE TABLE trips AS SELECT * FROM read_parquet(?)
        WHERE tpep_pickup_datetime >= TIMESTAMP '2024-01-01'
        AND tpep_pickup_datetime < TIMESTAMP '2024-02-01'
        ORDER BY tpep_pickup_datetime LIMIT ?""",
        [str(trip_path), row_limit],
    )
    connection.execute(
        "CREATE TABLE taxi_zones AS SELECT * FROM read_csv_auto(?)", [str(zone_path)]
    )
    connection.execute(
        """CREATE VIEW trips_enriched AS SELECT t.*, z.Borough AS pickup_borough,
        z.Zone AS pickup_zone FROM trips t LEFT JOIN taxi_zones z
        ON t.PULocationID = z.LocationID"""
    )
    count = connection.execute("SELECT count(*) FROM trips").fetchone()[0]
    connection.close()
    return count


def prepare_data(row_limit: int = 100_000, force: bool = False) -> int:
    trip_path = settings.data_dir / TRIP_FILE
    zone_path = settings.data_dir / ZONE_FILE
    if force or not trip_path.exists():
        download_file(TRIP_URL, trip_path)
    if force or not zone_path.exists():
        download_file(ZONE_URL, zone_path)
    validate_parquet(trip_path)
    validate_zones(zone_path)
    return build_database(trip_path, zone_path, settings.db_path, row_limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real NYC TLC data and build DuckDB")
    parser.add_argument("--row-limit", type=int, default=100_000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    count = prepare_data(args.row_limit, args.force)
    print(f"Loaded {count:,} real rows from {DATA_MONTH} into {settings.db_path}")


if __name__ == "__main__":
    main()
