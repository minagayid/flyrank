from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from signal_desk.database import reader, transaction

EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+$")
ALLOWED_FIELDS = {
    "full_name",
    "email",
    "company",
    "project_description",
    "budget_range",
    "timeline",
}


class ValidationError(ValueError):
    def __init__(self, fields: dict[str, str]):
        super().__init__("Lead input did not pass validation.")
        self.fields = fields


def validate_lead(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValidationError({"body": "Expected a JSON object."})
    errors: dict[str, str] = {}
    unknown = set(payload) - ALLOWED_FIELDS
    if unknown:
        errors["body"] = "Unknown fields are not accepted."

    normalized: dict[str, str] = {}
    limits = {
        "full_name": (1, 100, True),
        "email": (3, 254, True),
        "company": (0, 100, False),
        "project_description": (10, 2500, True),
        "budget_range": (0, 120, False),
        "timeline": (0, 120, False),
    }
    for field, (minimum, maximum, required) in limits.items():
        raw = payload.get(field, "")
        if not isinstance(raw, str):
            errors[field] = "Must be text."
            continue
        value = " ".join(raw.split())
        if required and not value:
            errors[field] = "This field is required."
        elif value and len(value) < minimum:
            errors[field] = f"Must contain at least {minimum} characters."
        elif len(value) > maximum:
            errors[field] = f"Must contain at most {maximum} characters."
        elif any(ord(char) < 32 and char not in "\t" for char in value):
            errors[field] = "Control characters are not accepted."
        elif field == "email" and value and not EMAIL_PATTERN.fullmatch(value):
            errors[field] = "Enter a valid email address."
        normalized[field] = value

    if errors:
        raise ValidationError(errors)
    return normalized


def create_lead(user_id: int, payload: Any) -> dict[str, Any]:
    lead = validate_lead(payload)
    lead_id = f"lead_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with transaction() as connection:
        connection.execute(
            """INSERT INTO leads(
                id, user_id, full_name, email, company, project_description,
                budget_range, timeline, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_id,
                user_id,
                lead["full_name"],
                lead["email"],
                lead["company"],
                lead["project_description"],
                lead["budget_range"],
                lead["timeline"],
                created_at,
            ),
        )
    return {"id": lead_id, **lead, "created_at": created_at}


def get_lead(user_id: int, lead_id: str) -> dict[str, Any] | None:
    with reader() as connection:
        row = connection.execute(
            """SELECT leads.*, triage_results.result_json, triage_results.created_at AS triaged_at
               FROM leads LEFT JOIN triage_results ON triage_results.lead_id = leads.id
               WHERE leads.id = ? AND leads.user_id = ?""",
            (lead_id, user_id),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["triage"] = result.pop("result_json")
    if result["triage"] is not None:
        import json

        result["triage"] = json.loads(result["triage"])
    return result


def list_leads(user_id: int) -> list[dict[str, Any]]:
    with reader() as connection:
        rows = connection.execute(
            """SELECT leads.id, leads.full_name, leads.company, leads.created_at,
                      triage_results.result_json, triage_results.created_at AS triaged_at
               FROM leads LEFT JOIN triage_results ON triage_results.lead_id = leads.id
               WHERE leads.user_id = ? ORDER BY leads.created_at DESC""",
            (user_id,),
        ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["triage"] = None
        if item.pop("result_json") is not None:
            import json

            item["triage"] = json.loads(row["result_json"])
        output.append(item)
    return output


def load_triage_input(user_id: int, lead_id: str) -> dict[str, Any] | None:
    with reader() as connection:
        row = connection.execute(
            """SELECT id, full_name, company, project_description, budget_range, timeline
               FROM leads WHERE id = ? AND user_id = ?""",
            (lead_id, user_id),
        ).fetchone()
    return dict(row) if row else None
