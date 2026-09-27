from __future__ import annotations

import re
from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, *, close: bool = False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.close = close


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_json_shape", f"{label} must be a JSON object")
    return value


def require_exact_keys(value: dict[str, Any], allowed: set[str], required: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise ApiError(422, "unknown_fields", f"{label} contains unsupported keys: {', '.join(unknown)}")
    if missing:
        raise ApiError(422, "missing_fields", f"{label} is missing required keys: {', '.join(missing)}")


def text(value: Any, label: str, *, maximum: int, minimum: int = 0, strip: bool = True) -> str:
    if not isinstance(value, str):
        raise ApiError(422, "invalid_field", f"{label} must be a string")
    cleaned = value.strip() if strip else value
    if len(cleaned) < minimum:
        raise ApiError(422, "invalid_field", f"{label} must contain at least {minimum} characters")
    if len(cleaned) > maximum:
        raise ApiError(422, "invalid_field", f"{label} must be at most {maximum} characters")
    if any(ord(char) < 32 and char not in "\r\n\t" for char in cleaned):
        raise ApiError(422, "invalid_field", f"{label} contains unsupported control characters")
    return cleaned


_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@.]+(?:\.[^\s@.]+)+$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{8,100}$")
_WIDGET_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_widget(payload: Any) -> dict[str, Any]:
    body = require_object(payload, "widget")
    allowed = {"type", "title", "description", "fields", "button_text", "display"}
    require_exact_keys(body, allowed, allowed, "widget")
    kind = body["type"]
    if not isinstance(kind, str) or kind not in {"signup", "contact", "cta"}:
        raise ApiError(422, "invalid_widget_type", "type must be signup, contact, or cta")
    title = text(body["title"], "title", maximum=80, minimum=1)
    description = text(body["description"], "description", maximum=240)
    button_text = text(body["button_text"], "button_text", maximum=40, minimum=1)
    fields_value = body["fields"]
    if not isinstance(fields_value, list) or not 1 <= len(fields_value) <= 6:
        raise ApiError(422, "invalid_fields", "fields must contain between 1 and 6 field definitions")
    fields: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, raw in enumerate(fields_value):
        definition = require_object(raw, f"fields[{index}]")
        expected = {"name", "label", "type", "required", "max_length"}
        require_exact_keys(definition, expected, expected, f"fields[{index}]")
        name = text(definition["name"], f"fields[{index}].name", maximum=40, minimum=1)
        if not _FIELD_NAME.fullmatch(name) or name in seen_names:
            raise ApiError(422, "invalid_field_name", f"fields[{index}].name is invalid or duplicated")
        seen_names.add(name)
        label = text(definition["label"], f"fields[{index}].label", maximum=60, minimum=1)
        field_type = definition["type"]
        if not isinstance(field_type, str) or field_type not in {"text", "email", "tel"}:
            raise ApiError(422, "invalid_field_type", f"fields[{index}].type must be text, email, or tel")
        required = definition["required"]
        if not isinstance(required, bool):
            raise ApiError(422, "invalid_field", f"fields[{index}].required must be boolean")
        max_length = definition["max_length"]
        if not isinstance(max_length, int) or isinstance(max_length, bool) or not 1 <= max_length <= 500:
            raise ApiError(422, "invalid_field", f"fields[{index}].max_length must be an integer from 1 to 500")
        fields.append({"name": name, "label": label, "type": field_type, "required": required, "max_length": max_length})
    display = require_object(body["display"], "display")
    require_exact_keys(display, {"theme", "position"}, {"theme", "position"}, "display")
    theme, position = display["theme"], display["position"]
    if (not isinstance(theme, str) or theme not in {"light", "dark"}
            or not isinstance(position, str) or position not in {"inline", "floating"}):
        raise ApiError(422, "invalid_display", "display.theme must be light or dark and display.position inline or floating")
    return {
        "type": kind,
        "title": title,
        "description": description,
        "fields": fields,
        "button_text": button_text,
        "display": {"theme": theme, "position": position},
    }


def validate_submission_envelope(payload: Any) -> dict[str, Any]:
    body = require_object(payload, "submission")
    require_exact_keys(body, {"widget_id", "fields", "company_website"}, {"widget_id", "fields", "company_website"}, "submission")
    widget_id = text(body["widget_id"], "widget_id", maximum=64, minimum=3)
    if not _WIDGET_ID.fullmatch(widget_id):
        raise ApiError(422, "invalid_widget_id", "widget_id contains unsupported characters")
    fields = require_object(body["fields"], "fields")
    if not 1 <= len(fields) <= 6:
        raise ApiError(422, "invalid_fields", "fields must contain between 1 and 6 values")
    website = text(body["company_website"], "company_website", maximum=500)
    return {"widget_id": widget_id, "fields": fields, "company_website": website}


def validate_idempotency_key(value: str | None) -> str:
    if value is None or not _IDEMPOTENCY.fullmatch(value):
        raise ApiError(400, "idempotency_key_required", "Idempotency-Key must contain 8 to 100 letters, digits, dots, underscores, colons, or hyphens")
    return value


def validate_submission_values(field_definitions: list[dict[str, Any]], values: dict[str, Any]) -> dict[str, str]:
    allowed = {definition["name"] for definition in field_definitions}
    extra = sorted(set(values) - allowed)
    if extra:
        raise ApiError(422, "unknown_submission_fields", f"fields contains unsupported names: {', '.join(extra)}")
    cleaned: dict[str, str] = {}
    for definition in field_definitions:
        name = definition["name"]
        value = values.get(name)
        if value is None:
            if definition["required"]:
                raise ApiError(422, "required_field", f"{definition['label']} is required")
            continue
        value = text(value, name, maximum=definition["max_length"])
        if not value and definition["required"]:
            raise ApiError(422, "required_field", f"{definition['label']} is required")
        if not value:
            continue
        if definition["type"] == "email" and not _EMAIL.fullmatch(value):
            raise ApiError(422, "invalid_email", f"{definition['label']} must be a valid email address")
        if definition["type"] == "tel" and not re.fullmatch(r"[+0-9() .-]{3,40}", value):
            raise ApiError(422, "invalid_phone", f"{definition['label']} must be a valid phone number")
        cleaned[name] = value
    return cleaned
