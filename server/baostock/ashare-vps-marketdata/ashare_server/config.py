from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("ASHARE_DATA_DIR", "/var/lib/ashare-marketdata"))
    api_host: str = os.getenv("ASHARE_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("ASHARE_API_PORT", "8765"))
    public_base_url: str = os.getenv("ASHARE_PUBLIC_BASE_URL", "").rstrip("/")
    history_days: int = int(os.getenv("ASHARE_HISTORY_DAYS", "120"))
    retention_days: int = int(os.getenv("ASHARE_RETENTION_DAYS", "120"))
    batch_size: int = int(os.getenv("ASHARE_BATCH_SIZE", "200"))
    batch_pause: float = float(os.getenv("ASHARE_BATCH_PAUSE", "2.0"))
    max_consecutive_errors: int = int(os.getenv("ASHARE_MAX_CONSECUTIVE_ERRORS", "25"))
    max_api_requests_per_day: int = int(os.getenv("ASHARE_MAX_API_REQUESTS_PER_DAY", "45000"))
    retry_base_hours: int = int(os.getenv("ASHARE_RETRY_BASE_HOURS", "6"))
    retry_max_hours: int = int(os.getenv("ASHARE_RETRY_MAX_HOURS", "168"))
    industry_refresh_days: int = int(os.getenv("ASHARE_INDUSTRY_REFRESH_DAYS", "7"))
    min_publish_completeness: float = float(os.getenv("ASHARE_MIN_PUBLISH_COMPLETENESS", "0.995"))
    api_log_level: str = os.getenv("ASHARE_LOG_LEVEL", "INFO").upper()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "market-unadjusted.sqlite3"

    @property
    def public_dir(self) -> Path:
        return self.data_dir / "public"

    @property
    def snapshot_path(self) -> Path:
        return self.public_dir / "snapshot.zip"

    @property
    def manifest_path(self) -> Path:
        return self.public_dir / "latest.json"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "update.lock"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "logs"


settings = Settings()
