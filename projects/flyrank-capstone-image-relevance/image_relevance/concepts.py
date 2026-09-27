"""Small, inspectable vocabulary used by the deterministic demo embedding model."""

from __future__ import annotations

import re


SUBJECT_ALIASES: dict[str, str] = {
    "vulpes vulpes": "red fox",
    "red foxes": "red fox",
    "fox": "red fox",
    "foxes": "red fox",
    "canis lupus": "gray wolf",
    "grey wolf": "gray wolf",
    "wolves": "gray wolf",
    "wolf": "gray wolf",
    "canis lupus familiaris": "domestic dog",
    "domestic dogs": "domestic dog",
    "dogs": "domestic dog",
    "dog": "domestic dog",
    "brown bear": "bear",
    "bears": "bear",
    "white tailed deer": "deer",
    "white tail deer": "deer",
    "deer": "deer",
    "barn owls": "barn owl",
    "owl": "barn owl",
    "owls": "barn owl",
    "apples": "apple",
    "heirloom apple": "apple",
    "strawberries": "strawberry",
    "strawberry": "strawberry",
    "sourdough": "sourdough bread",
    "sunflowers": "sunflower",
    "oak": "oak tree",
    "oak trees": "oak tree",
    "roses": "rose",
    "eiffel tower": "eiffel tower",
    "tower eiffel": "eiffel tower",
    "lighthouse": "lighthouse",
    "light house": "lighthouse",
}

SUBJECT_CATEGORY: dict[str, str] = {
    "red fox": "animal",
    "gray wolf": "animal",
    "domestic dog": "animal",
    "bear": "animal",
    "deer": "animal",
    "barn owl": "animal",
    "apple": "food",
    "strawberry": "food",
    "sourdough bread": "food",
    "sunflower": "plant",
    "oak tree": "plant",
    "rose": "plant",
    "eiffel tower": "landmark",
    "lighthouse": "landmark",
}


def _pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", re.IGNORECASE)


_CANONICAL_SUBJECTS = sorted(SUBJECT_CATEGORY, key=len, reverse=True)
_NORMALIZATION_MAP = {alias.lower(): canonical for alias, canonical in SUBJECT_ALIASES.items()}
_NORMALIZATION_MAP.update({subject: subject for subject in SUBJECT_CATEGORY})
_ALIASES_LONGEST_FIRST = sorted(_NORMALIZATION_MAP.items(), key=lambda item: len(item[0]), reverse=True)
_ALIAS_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(alias) for alias, _ in _ALIASES_LONGEST_FIRST) +
    r")(?![a-z0-9])",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Replace known aliases with their canonical phrase without an external model."""
    return _ALIAS_PATTERN.sub(lambda match: _NORMALIZATION_MAP[match.group(0).lower()], text.lower())


def normalize_subject(subject: str) -> str:
    return normalize_text(subject).strip()


def detect_subjects(text: str) -> list[str]:
    """Return canonical subjects mentioned in text, longest phrase first."""
    normalized = normalize_text(text)
    found: list[str] = []
    for subject in _CANONICAL_SUBJECTS:
        if _pattern(subject).search(normalized) and subject not in found:
            found.append(subject)
    return found


def infer_category(text: str) -> str | None:
    subjects = detect_subjects(text)
    if subjects:
        categories = {SUBJECT_CATEGORY[subject] for subject in subjects}
        return next(iter(categories)) if len(categories) == 1 else None
    normalized = normalize_text(text)
    cues = {
        "animal": ("animal", "wildlife", "species", "habitat"),
        "food": ("recipe", "ingredient", "baking", "breakfast", "fruit"),
        "plant": ("botany", "flower", "tree", "garden", "plant"),
        "landmark": ("architecture", "monument", "landmark", "tourist site"),
    }
    matches = [category for category, words in cues.items() if any(_pattern(word).search(normalized) for word in words)]
    return matches[0] if len(matches) == 1 else None
