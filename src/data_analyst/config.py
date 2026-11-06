"""Small, centralized application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    db_path: Path = Path(os.getenv("DB_PATH", "data/taxi.duckdb"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    max_result_rows: int = int(os.getenv("MAX_RESULT_ROWS", "500"))
    query_timeout_seconds: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    metrics_port: int = int(os.getenv("METRICS_PORT", "8001"))


settings = Settings()
