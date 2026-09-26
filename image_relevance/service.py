"""Application service layer for ranking, mismatch inspection, and review persistence."""

from __future__ import annotations

from typing import Any

from .matching import mismatch_guard, rank_candidates
from .repository import Repository


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class MatchingService:
    def __init__(self, repository: Repository, similarity_threshold: float, confidence_threshold: float) -> None:
        self.repository = repository
        self.similarity_threshold = similarity_threshold
        self.confidence_threshold = confidence_threshold

    def _ranked(self, tenant_id: str, post_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        post = self.repository.get_post(tenant_id, post_id)
        if post is None:
            raise ServiceError(404, "post_not_found", "Post was not found for this tenant")
        if not isinstance(post.get("embedding"), list):
            raise ServiceError(409, "post_not_processed", "Run the asynchronous corpus job before requesting matches")
        images = self.repository.list_images(tenant_id, ready_only=True)
        ranked = rank_candidates(post, post["embedding"], images, self.similarity_threshold, self.confidence_threshold)
        if not ranked:
            raise ServiceError(409, "images_not_processed", "No validated image tags and embeddings are available yet")
        return post, ranked

    @staticmethod
    def _public_candidate(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: item[key]
            for key in ("image_id", "reference", "subject", "caption", "similarity", "accepted", "reasons")
        }

    def recommendations(self, tenant_id: str, post_id: str, candidate_id: str | None = None) -> dict[str, Any]:
        post, ranked = self._ranked(tenant_id, post_id)
        if candidate_id:
            image = self.repository.get_image(tenant_id, candidate_id)
            if image is None:
                raise ServiceError(404, "image_not_found", "Candidate image was not found for this tenant")
            if not image.get("tags") or not isinstance(image.get("embedding"), list):
                raise ServiceError(409, "image_not_processed", "Candidate image has not completed the batch job")
            item = next((candidate for candidate in ranked if candidate["image_id"] == candidate_id), None)
            if item is None:
                raise ServiceError(409, "candidate_unavailable", "Candidate could not be ranked")
            return {
                "post_id": post_id,
                "status": "accepted" if item["accepted"] else "rejected",
                "forced_candidate": self._public_candidate(item),
                "explanation": "Candidate passed the mismatch guard." if item["accepted"] else "; ".join(item["reasons"]),
            }

        accepted = [item for item in ranked if item["accepted"]]
        if accepted:
            return {
                "post_id": post_id,
                "status": "matched",
                "suggested_image": self._public_candidate(accepted[0]),
                "recommendations": [self._public_candidate(item) for item in accepted[:5]],
                "ranked_candidates": [self._public_candidate(item) for item in ranked[:10]],
                "explanation": "The highest-ranked candidate cleared subject, confidence, and similarity checks.",
                "thresholds": {
                    "similarity": self.similarity_threshold,
                    "confidence": self.confidence_threshold,
                },
            }
        best = ranked[0]
        reasons = list(best["reasons"])
        if not reasons:
            reasons = ["No candidate cleared the mismatch guard"]
        return {
            "post_id": post_id,
            "status": "no_confident_match",
            "suggested_image": None,
            "recommendations": [],
            "ranked_candidates": [self._public_candidate(item) for item in ranked[:10]],
            "explanation": "No image cleared the mismatch guard; the service refused to guess.",
            "reasons": reasons,
            "thresholds": {
                "similarity": self.similarity_threshold,
                "confidence": self.confidence_threshold,
            },
        }

    def create_suggestions(self, tenant_id: str, post_id: str, idempotency_key: str) -> tuple[dict[str, Any], bool]:
        post, ranked = self._ranked(tenant_id, post_id)
        del post
        try:
            run_id, created = self.repository.create_suggestion_run(tenant_id, post_id, idempotency_key, ranked[:10])
        except ValueError as exc:
            raise ServiceError(409, "idempotency_conflict", str(exc)) from exc
        suggestions = [item for item in self.repository.list_suggestions(tenant_id, post_id) if item["run_id"] == run_id]
        accepted = next((item for item in suggestions if item["accepted"]), None)
        return {
            "run_id": run_id,
            "post_id": post_id,
            "status": "matched" if accepted else "no_confident_match",
            "suggested_image": accepted,
            "suggestions": suggestions,
        }, created

    def get_suggestion(self, tenant_id: str, suggestion_id: str) -> dict[str, Any]:
        suggestion = self.repository.get_suggestion(tenant_id, suggestion_id)
        if suggestion is None:
            raise ServiceError(404, "suggestion_not_found", "Suggestion was not found for this tenant")
        return suggestion
