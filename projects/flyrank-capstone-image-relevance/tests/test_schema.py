from __future__ import annotations

import json
import unittest
from pathlib import Path

from image_relevance.concepts import detect_subjects, normalize_text
from image_relevance.schema import SchemaValidationError, validate_vision_output


ROOT = Path(__file__).resolve().parents[1]


class VisionSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = {
            "subject": "red fox",
            "category": "animal",
            "attributes": ["orange fur", "forest"],
            "caption": "A red fox standing in a forest",
            "confidence": 0.94,
        }

    def test_valid_output_is_typed(self) -> None:
        result = validate_vision_output(self.valid)
        self.assertEqual(result.subject, "red fox")
        self.assertAlmostEqual(result.confidence, 0.94)

    def test_missing_extra_and_bad_confidence_are_rejected(self) -> None:
        missing = dict(self.valid)
        missing.pop("caption")
        extra = {**self.valid, "filename": "fox.jpg"}
        bool_confidence = {**self.valid, "confidence": True}
        for payload in (missing, extra, bool_confidence):
            with self.subTest(payload=payload):
                with self.assertRaises(SchemaValidationError):
                    validate_vision_output(payload)
        print("ACCEPTANCE_PROOF vision_schema valid=accepted invalid_missing_extra_bool_confidence=3_rejected")

    def test_known_equivalent_concept_maps_to_canonical_subject(self) -> None:
        self.assertEqual(normalize_text("Vulpes vulpes"), "red fox")
        self.assertIn("red fox", detect_subjects("A guide to Vulpes vulpes and its habitat"))
        print("ACCEPTANCE_PROOF semantic_alias Vulpes_vulpes=red_fox")

    def test_fixture_corpus_is_bounded_and_labeled(self) -> None:
        corpus = json.loads((ROOT / "fixtures" / "corpus.json").read_text(encoding="utf-8"))
        evaluation = json.loads((ROOT / "fixtures" / "eval.json").read_text(encoding="utf-8"))
        categories = {entry["vision_output"]["category"] for entry in corpus["images"]}
        self.assertEqual(len(corpus["images"]), 48)
        self.assertGreaterEqual(len(categories), 4)
        self.assertEqual(len(evaluation["labels"]), 12)
        print(
            f"ACCEPTANCE_PROOF corpus images={len(corpus['images'])} categories={len(categories)} "
            f"posts={len(corpus['posts'])} labeled_pairs={len(evaluation['labels'])}"
        )


if __name__ == "__main__":
    unittest.main()
