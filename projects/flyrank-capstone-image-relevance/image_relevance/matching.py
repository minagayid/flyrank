"""Similarity ranking and explicit refusal decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .concepts import SUBJECT_CATEGORY, detect_subjects, infer_category, normalize_subject
from .embeddings import cosine_similarity
from .schema import SchemaValidationError, validate_vision_output


@dataclass(frozen=True)
class GuardDecision:
    accepted: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def mismatch_guard(
    post_text: str,
    tags: dict[str, object],
    similarity: float,
    similarity_threshold: float,
    confidence_threshold: float,
) -> GuardDecision:
    reasons: list[str] = []
    try:
        validated = validate_vision_output(tags)
    except SchemaValidationError as exc:
        return GuardDecision(False, [f"Invalid image tags: {exc}"])

    expected_subjects = detect_subjects(post_text)
    expected_category = infer_category(post_text)
    detected_subject = normalize_subject(validated.subject)
    if expected_subjects and detected_subject not in expected_subjects:
        expected = " or ".join(expected_subjects)
        if expected_category and validated.category == expected_category:
            reasons.append(
                f"{expected_category.title()} category mismatch: expected {expected}, detected {detected_subject} "
                f"(subject mismatch within {expected_category})"
            )
        else:
            reasons.append(f"Subject mismatch: expected {expected}, detected {detected_subject}")
    if expected_category and validated.category != expected_category:
        reasons.append(f"Category mismatch: expected {expected_category}, detected {validated.category}")
    if validated.confidence < confidence_threshold:
        reasons.append(
            f"Low-confidence classification: {validated.confidence:.2f} is below {confidence_threshold:.2f}"
        )
    if similarity < similarity_threshold:
        reasons.append(f"Similarity {similarity:.3f} is below {similarity_threshold:.3f}")
    return GuardDecision(not reasons, reasons)


def rank_candidates(
    post: dict[str, str],
    post_vector: list[float],
    images: list[dict[str, object]],
    similarity_threshold: float,
    confidence_threshold: float,
) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    post_text = f"{post['title']} {post['body']}"
    for image in images:
        tags = image.get("tags")
        vector = image.get("embedding")
        if not isinstance(tags, dict) or not isinstance(vector, list):
            continue
        score = cosine_similarity(post_vector, vector)
        decision = mismatch_guard(post_text, tags, score, similarity_threshold, confidence_threshold)
        ranked.append(
            {
                "image_id": image["image_id"],
                "reference": image["reference"],
                "subject": tags.get("subject"),
                "caption": tags.get("caption"),
                "similarity": round(score, 4),
                "accepted": decision.accepted,
                "reasons": decision.reasons,
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["similarity"]), str(item["image_id"])))
