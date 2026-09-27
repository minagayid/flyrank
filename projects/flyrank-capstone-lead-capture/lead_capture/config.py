from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
DEMO_TENANT_A_TOKEN = "local-demo-tenant-a-only-change-before-hosting-123"
DEMO_TENANT_B_TOKEN = "local-demo-tenant-b-only-change-before-hosting-456"


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def load_env_file(path: Path | None = None) -> None:
    """Load simple KEY=VALUE entries without a third-party dotenv dependency."""
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(value[0]):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    root: Path
    database_path: Path
    api_host: str
    api_port: int
    demo_host: str
    demo_port: int
    public_base_url: str
    widget_bundle_version: str
    max_request_bytes: int
    rate_bucket_capacity: int
    rate_refill_per_second: float
    ip_admission_bucket_capacity: int
    ip_admission_refill_per_second: float
    geo_mode: str
    mock_geo_a_down: bool
    mock_geo_b_down: bool
    mock_notification_fail: bool
    allow_dev_controls: bool
    notification_max_attempts: int
    tenant_a_token: str
    tenant_b_token: str
    ip_hash_salt: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        root = ROOT
        raw_db = Path(os.getenv("DB_PATH", "data/lead-capture.sqlite3"))
        database_path = raw_db if raw_db.is_absolute() else root / raw_db
        public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        api_host = os.getenv("API_HOST", "127.0.0.1")
        bundle = os.getenv("WIDGET_BUNDLE_VERSION", "v1")
        if not re.fullmatch(r"v[1-9][0-9]*", bundle):
            raise ValueError("WIDGET_BUNDLE_VERSION must look like v1, v2, and so on")
        geo_mode = os.getenv("GEO_MODE", "mock").strip().lower()
        if geo_mode != "mock":
            raise ValueError("GEO_MODE must be mock; outbound geolocation is disabled to protect visitor IPs")
        allow_dev_controls = _bool("ALLOW_DEV_CONTROLS", False)
        tenant_a_token = os.getenv("DEMO_TENANT_A_TOKEN", DEMO_TENANT_A_TOKEN)
        tenant_b_token = os.getenv("DEMO_TENANT_B_TOKEN", DEMO_TENANT_B_TOKEN)
        public_host = urlsplit(public_base_url).hostname
        if not (_is_loopback_host(api_host) and _is_loopback_host(public_host)):
            if tenant_a_token == DEMO_TENANT_A_TOKEN or tenant_b_token == DEMO_TENANT_B_TOKEN:
                raise ValueError("Non-loopback API/PUBLIC_BASE_URL requires replacing both public demo owner tokens")
            if allow_dev_controls:
                raise ValueError("ALLOW_DEV_CONTROLS must be false for non-loopback API/PUBLIC_BASE_URL")
        return cls(
            root=root,
            database_path=database_path,
            api_host=api_host,
            api_port=_int("API_PORT", 8000, 1, 65535),
            demo_host=os.getenv("DEMO_HOST", "127.0.0.1"),
            demo_port=_int("DEMO_PORT", 4173, 1, 65535),
            public_base_url=public_base_url,
            widget_bundle_version=bundle,
            max_request_bytes=_int("MAX_REQUEST_BYTES", 16384, 1024, 1048576),
            rate_bucket_capacity=_int("RATE_BUCKET_CAPACITY", 3, 1, 1000),
            rate_refill_per_second=_float("RATE_REFILL_PER_SECOND", 2.0, 0.01, 1000.0),
            ip_admission_bucket_capacity=_int("IP_ADMISSION_BUCKET_CAPACITY", 20, 1, 10000),
            ip_admission_refill_per_second=_float("IP_ADMISSION_REFILL_PER_SECOND", 10.0, 0.01, 1000.0),
            geo_mode=geo_mode,
            mock_geo_a_down=_bool("MOCK_GEO_A_DOWN", False),
            mock_geo_b_down=_bool("MOCK_GEO_B_DOWN", False),
            mock_notification_fail=_bool("MOCK_NOTIFICATION_FAIL", False),
            allow_dev_controls=allow_dev_controls,
            notification_max_attempts=_int("NOTIFICATION_MAX_ATTEMPTS", 3, 1, 10),
            tenant_a_token=tenant_a_token,
            tenant_b_token=tenant_b_token,
            ip_hash_salt=os.getenv("IP_HASH_SALT", "local-demo-only-change-before-hosting"),
        )
