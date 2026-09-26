"""Regenerate the small deterministic mock vision corpus and labeled eval set."""

from __future__ import annotations

import json
from pathlib import Path


SUBJECTS = [
    ("red fox", "animal", ["amber coat", "pine woodland", "dawn light"]),
    ("gray wolf", "animal", ["moonlit pack", "alpine tundra", "winter trail"]),
    ("domestic dog", "animal", ["service vest", "school hallway", "guide training"]),
    ("bear", "animal", ["salmon river", "mossy rocks", "autumn valley"]),
    ("deer", "animal", ["fern clearing", "morning mist", "woodland path"]),
    ("barn owl", "animal", ["dusk flight", "old red barn", "silent meadow"]),
    ("apple", "food", ["heirloom orchard", "crisp red skin", "harvest basket"]),
    ("strawberry", "food", ["summer market", "ripe berry", "garden patch"]),
    ("sourdough bread", "food", ["open crumb", "scored crust", "flour dust"]),
    ("sunflower", "plant", ["golden petals", "pollinator garden", "late summer"]),
    ("oak tree", "plant", ["acorn branch", "autumn canopy", "old woodland"]),
    ("eiffel tower", "landmark", ["iron lattice", "paris skyline", "river view"]),
]

ALTERNATES = [
    ("snowy ridge", "cool blue light"),
    ("sheltered den", "soft shadow"),
    ("open meadow", "cloudy afternoon"),
]

POSTS = [
    ("post-red-fox", "Vulpes vulpes at dawn", "A field guide to the red fox Vulpes vulpes, its amber coat and pine woodland habitat at dawn.", "img-red-fox-01"),
    ("post-gray-wolf", "Gray wolves on the alpine trail", "A wildlife article about the gray wolf pack crossing alpine tundra on a moonlit winter trail.", "img-gray-wolf-01"),
    ("post-domestic-dog", "Service dogs in schools", "How a trained domestic dog in a service vest supports students in a school hallway during guide training.", "img-domestic-dog-01"),
    ("post-bear", "Bears beside salmon rivers", "An animal profile of a bear fishing for salmon beside mossy rocks in an autumn valley.", "img-bear-01"),
    ("post-deer", "Deer in a fern clearing", "A nature story about deer on a woodland path through a fern clearing in the morning mist.", "img-deer-01"),
    ("post-barn-owl", "Barn owl flight at dusk", "A wildlife note on a barn owl making a silent flight past an old red barn above a meadow at dusk.", "img-barn-owl-01"),
    ("post-apple", "Heirloom apples from the orchard", "A food feature about a crisp heirloom apple with red skin picked into a harvest basket in the orchard.", "img-apple-01"),
    ("post-strawberry", "Ripe strawberries in summer", "A recipe story about ripe strawberries gathered from a garden patch for the summer market.", "img-strawberry-01"),
    ("post-sourdough", "Reading sourdough crumb", "A baking guide to sourdough bread with an open crumb, scored crust, and a dusting of flour.", "img-sourdough-bread-01"),
    ("post-sunflower", "Sunflowers and pollinators", "A plant profile of a sunflower with golden petals growing in a pollinator garden in late summer.", "img-sunflower-01"),
    ("post-oak", "Oak trees in autumn", "A botany article about an oak tree with an acorn branch beneath its autumn canopy in old woodland.", "img-oak-tree-01"),
    ("post-eiffel", "The Eiffel Tower and the river", "An architecture feature on the Eiffel Tower's iron lattice, Paris skyline, and river view.", "img-eiffel-tower-01"),
]


def build() -> tuple[dict[str, object], dict[str, object]]:
    images: list[dict[str, object]] = []
    for subject, category, target_attributes in SUBJECTS:
        variants = [target_attributes, *ALTERNATES]
        for index, attributes in enumerate(variants, start=1):
            image_id = f"img-{subject.replace(' ', '-')}-{index:02d}"
            caption = f"A {subject} showing " + " and ".join(attributes)
            confidence = 0.48 if subject == "strawberry" and index == 4 else 0.94
            item: dict[str, object] = {
                "image_id": image_id,
                "reference": f"mock://flyrank-demo/{image_id}.jpg",
                "vision_output": {
                    "subject": subject,
                    "category": category,
                    "attributes": attributes,
                    "caption": caption,
                    "confidence": confidence,
                },
                "invalid_first_attempts": 1 if image_id == "img-red-fox-04" else 0,
            }
            images.append(item)
    corpus = {
        "schema_version": 1,
        "provider": "mock-vision-v1",
        "images": images,
        "posts": [
            *[{"post_id": pid, "title": title, "body": body} for pid, title, body, _ in POSTS],
            {
                "post_id": "post-no-match",
                "title": "Quantum ceramic catalyst notes",
                "body": "A technical note about a lab catalyst with no image in this corpus.",
            },
        ],
    }
    evaluation = {
        "schema_version": 1,
        "description": "Twelve hand-labeled post-to-image pairs over the synthetic demo corpus.",
        "labels": [{"post_id": pid, "correct_image_id": image_id} for pid, _, _, image_id in POSTS],
        "probes": {
            "forced_mismatch": {"post_id": "post-red-fox", "image_id": "img-gray-wolf-01"},
            "no_match_post": {
                "post_id": "post-no-match",
            },
            "low_confidence_image_id": "img-strawberry-04",
            "retry_image_id": "img-red-fox-04",
        },
    }
    return corpus, evaluation


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    corpus, evaluation = build()
    (root / "corpus.json").write_text(json.dumps(corpus, indent=2) + "\n", encoding="utf-8")
    (root / "eval.json").write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(corpus['images'])} image fixtures, {len(corpus['posts'])} posts, and {len(evaluation['labels'])} eval labels.")
