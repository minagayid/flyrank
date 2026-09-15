import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validation_style import (
    build_run_provenance,
    metric_provenance_error,
    require_metric_provenance,
    validation_style,
)


class ValidationStyleTests(unittest.TestCase):
    def test_client_holdout_is_described_as_grouped(self):
        label, detail = validation_style({"split_strategy": "client_holdout"})
        self.assertEqual(label, "client holdout")
        self.assertIn("Entire anonymized clients", detail)

    def test_row_fallback_does_not_claim_new_client_generalization(self):
        label, detail = validation_style({"split_strategy": "stratified_row_holdout"})
        self.assertEqual(label, "stratified row holdout")
        self.assertIn("does not establish new-client generalization", detail)

    def test_missing_or_unknown_strategy_fails_closed_in_the_report(self):
        for results in ({}, {"split_strategy": "unexpected"}, None):
            with self.subTest(results=results):
                label, detail = validation_style(results)
                self.assertEqual(label, "unspecified")
                self.assertIn("did not record a recognized", detail)

    def test_metric_publication_requires_matching_data_code_seed_and_split_lineage(self):
        result = {
            "split_strategy": "client_holdout",
            "run_provenance": build_run_provenance(
                feature_data_sha256="a" * 64,
                baseline_data_sha256="b" * 64,
                code_bundle_sha256="c" * 64,
                random_seed=42,
                split_strategy="client_holdout",
            ),
        }
        self.assertIsNone(metric_provenance_error(result))
        require_metric_provenance(result)

        result["run_provenance"]["feature_data_sha256"] = "d" * 64
        self.assertIn("run identifier", metric_provenance_error(result))

    def test_missing_provenance_blocks_metrics_even_when_split_is_known(self):
        result = {"split_strategy": "client_holdout"}
        self.assertIn("run provenance", metric_provenance_error(result))
        with self.assertRaisesRegex(ValueError, "run provenance"):
            require_metric_provenance(result)

    def test_agent_narration_matches_the_withdrawn_sample_claim(self):
        agent_html = (Path(__file__).resolve().parents[1] / "agent" / "index.html").read_text(encoding="utf-8")
        self.assertIn("No reproducible score comparison is currently claimed", agent_html)
        self.assertNotIn("two measured precision values", agent_html.lower())

    def test_readme_does_not_present_withdrawn_static_precision_values(self):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("static precision@50 comparisons have been withdrawn", readme)
        self.assertNotIn("precision@50 ≈ 0.24 → 0.74", readme)


if __name__ == "__main__":
    unittest.main()
