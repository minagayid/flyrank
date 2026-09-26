"""Measure guarded top-1 precision on the small labeled fixture set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import CONFIDENCE_THRESHOLD, DATABASE_PATH, SIMILARITY_THRESHOLD
from .database import Database
from .matching import rank_candidates
from .repository import Repository
from .seed import FIXTURE_DIR, read_json


def evaluate_repository(repository: Repository, evaluation: dict[str, Any], tenant_id: str = "demo") -> dict[str, Any]:
    labels = evaluation["labels"]
    outcomes: list[dict[str, Any]] = []
    for label in labels:
        post = repository.get_post(tenant_id, label["post_id"])
        if post is None or not isinstance(post.get("embedding"), list):
            raise RuntimeError(f"post {label['post_id']} has no stored embedding; finish the batch job first")
        images = repository.list_images(tenant_id, ready_only=True)
        ranked = rank_candidates(post, post["embedding"], images, SIMILARITY_THRESHOLD, CONFIDENCE_THRESHOLD)
        top = next((item for item in ranked if item["accepted"]), None)
        outcomes.append(
            {
                "post_id": label["post_id"],
                "expected_image_id": label["correct_image_id"],
                "predicted_image_id": top["image_id"] if top else None,
                "correct": bool(top and top["image_id"] == label["correct_image_id"]),
                "similarity": top["similarity"] if top else None,
            }
        )
    correct = sum(1 for result in outcomes if result["correct"])
    total = len(outcomes)
    return {"correct": correct, "total": total, "precision": correct / total if total else 0.0, "outcomes": outcomes}


def main() -> None:
    database = Database(DATABASE_PATH)
    database.initialize()
    repository = Repository(database)
    evaluation = read_json(FIXTURE_DIR / "eval.json")
    try:
        result = evaluate_repository(repository, evaluation)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Guarded top-1 precision: {result['correct']}/{result['total']} = {result['precision']:.3f}")
    for outcome in result["outcomes"]:
        marker = "PASS" if outcome["correct"] else "FAIL"
        print(f"{marker} {outcome['post_id']}: {outcome['predicted_image_id']} (expected {outcome['expected_image_id']})")


if __name__ == "__main__":
    main()
