from __future__ import annotations

import sys

from .config import Settings
from .db import connect, digest, json_dump, migrate, utc_now


TENANTS = (
    ("tenant_demo_a", "Demo Workspace A", "seed-demo-owner-a"),
    ("tenant_demo_b", "Demo Workspace B", "seed-demo-owner-b"),
)
WIDGET_ID = "widget_demo_signup"
WIDGET = {
    "type": "signup",
    "title": "Get the field guide",
    "description": "Leave your details and we will send the demo guide.",
    "fields": [
        {"name": "name", "label": "Name", "type": "text", "required": True, "max_length": 120},
        {"name": "email", "label": "Email", "type": "email", "required": True, "max_length": 254},
    ],
    "button_text": "Send me the guide",
    "display": {"theme": "light", "position": "inline"},
}


def seed(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    if settings.tenant_a_token == settings.tenant_b_token:
        raise ValueError("Demo owner tokens must be different")
    migrate(settings)
    now = utc_now()
    with connect(settings) as connection:
        for (tenant_id, name, label), token in zip(TENANTS, (settings.tenant_a_token, settings.tenant_b_token), strict=True):
            connection.execute(
                "INSERT INTO tenants(id, name, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name",
                (tenant_id, name, now),
            )
            connection.execute("DELETE FROM api_tokens WHERE tenant_id=? AND label=?", (tenant_id, label))
            connection.execute(
                "INSERT INTO api_tokens(token_hash, tenant_id, label, created_at) VALUES (?, ?, ?, ?)",
                (digest(token), tenant_id, label, now),
            )
        connection.execute(
            "INSERT OR IGNORE INTO widgets "
            "(id, tenant_id, type, title, description, fields_json, button_text, display_json, enabled, version, created_at, updated_at) "
            "VALUES (?, 'tenant_demo_a', ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)",
            (
                WIDGET_ID,
                WIDGET["type"],
                WIDGET["title"],
                WIDGET["description"],
                json_dump(WIDGET["fields"]),
                WIDGET["button_text"],
                json_dump(WIDGET["display"]),
                now,
                now,
            ),
        )
    print(f"Seeded local tenants: {TENANTS[0][0]}, {TENANTS[1][0]}")
    print(f"Seeded local widget: {WIDGET_ID}")
    print("Demo tokens are read from .env and are never printed.")


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        print(f"Seed failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
