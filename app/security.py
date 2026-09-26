from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import HTTPException

from app.db import read_connection


def key_digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def authenticate_tenant(tenant_id: str | None, tenant_key: str | None) -> dict[str, Any]:
    if not tenant_id or not tenant_key:
        raise HTTPException(status_code=401, detail={"code": "tenant_auth_required", "message": "Provide X-Tenant-ID and X-Tenant-Key."})
    with read_connection() as connection:
        row = connection.execute(
            "SELECT id, name, api_key_hash FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
    if row is None or not hmac.compare_digest(row["api_key_hash"], key_digest(tenant_key)):
        raise HTTPException(status_code=401, detail={"code": "tenant_auth_failed", "message": "Tenant credentials were not accepted."})
    return {"id": row["id"], "name": row["name"]}


def request_fingerprint(method: str, path: str, payload: dict[str, Any]) -> str:
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    material = f"{method.upper()}\n{path}\n{canonical}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()
