"""Strict boundary validation for mock or future vision-provider responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when untrusted model output does not match the vision contract."""


@dataclass(frozen=True)
class VisionOutput:
    subject: str
    category: str
    attributes: list[str]
    caption: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


VISION_KEYS = {"subject", "category", "attributes", "caption", "confidence"}
ALLOWED_CATEGORIES = {"animal", "food", "plant", "landmark"}


def validate_vision_output(payload: Any) -> VisionOutput:
    if not isinstance(payload, dict):
        raise SchemaValidationError("vision output must be a JSON object")
    actual = set(payload)
    missing = VISION_KEYS - actual
    extra = actual - VISION_KEYS
    if missing:
        raise SchemaValidationError(f"missing required fields: {', '.join(sorted(missing))}")
    if extra:
        raise SchemaValidationError(f"unexpected fields: {', '.join(sorted(extra))}")

    subject = payload["subject"]
    category = payload["category"]
    caption = payload["caption"]
    attributes = payload["attributes"]
    confidence = payload["confidence"]
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 120:
        raise SchemaValidationError("subject must be a non-empty string of at most 120 characters")
    if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
        raise SchemaValidationError(f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")
    if not isinstance(attributes, list) or len(attributes) > 12:
        raise SchemaValidationError("attributes must be a list containing at most 12 strings")
    if any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in attributes):
        raise SchemaValidationError("each attribute must be a non-empty string of at most 80 characters")
    if not isinstance(caption, str) or not caption.strip() or len(caption) > 240:
        raise SchemaValidationError("caption must be a non-empty string of at most 240 characters")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise SchemaValidationError("confidence must be a number between 0 and 1")
    return VisionOutput(subject.strip(), category, list(attributes), caption.strip(), float(confidence))
