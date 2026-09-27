from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from image_relevance.api import create_server
from image_relevance.config import CONFIDENCE_THRESHOLD, SIMILARITY_THRESHOLD
from image_relevance.database import Database
from image_relevance.evaluate import evaluate_repository
from image_relevance.repository import Repository
from image_relevance.seed import FIXTURE_DIR, read_json


class AcceptanceProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="image-relevance-")
        database_path = Path(cls.temp_dir.name) / "acceptance.sqlite3"
        cls.server = create_server(
            str(database_path),
            "127.0.0.1",
            0,
            SIMILARITY_THRESHOLD,
            CONFIDENCE_THRESHOLD,
            0.10,
            2,
            embedding_provider="hash",
        )
        cls.server.RequestHandlerClass.log_message = lambda *args: None
        cls.repository = cls.server.app.repository
        corpus = read_json(FIXTURE_DIR / "corpus.json")
        cls.repository.seed_corpus("demo", corpus)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        status, response = cls.request("POST", "/jobs", {"kind": "process-corpus"}, {"Idempotency-Key": "acceptance-batch-v1"})
        if status != 202:
            raise AssertionError(f"batch job did not start: {status} {response}")
        cls.job_id = response["job"]["job_id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            _, job = cls.request("GET", f"/jobs/{cls.job_id}")
            if job["status"] in {"completed", "completed_with_warnings", "failed"}:
                cls.final_job = job
                break
            time.sleep(0.1)
        else:
            raise AssertionError("async batch did not finish within 15 seconds")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        cls.temp_dir.cleanup()

    @classmethod
    def request(
        cls,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        request_headers = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(cls.base_url + path, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_background_job_retries_flags_and_tracks_every_call(self) -> None:
        self.assertEqual(self.final_job["status"], "completed")
        self.assertEqual(self.final_job["progress"]["completed_items"], 61)
        self.assertEqual(self.final_job["progress"]["failed_items"], 0)
        self.assertEqual(self.final_job["progress"]["percent"], 100.0)
        self.assertEqual(self.final_job["retries"], 1)
        self.assertEqual(self.final_job["low_confidence_items"], 1)
        self.assertEqual(self.final_job["cost_calls"]["vision"]["calls"], 49)
        self.assertEqual(self.final_job["cost_calls"]["embedding"]["calls"], 61)
        self.assertEqual(self.final_job["cost_usd"], 0.0)
        duplicate_status, duplicate = self.request(
            "POST", "/jobs", {"kind": "process-corpus"}, {"Idempotency-Key": "acceptance-batch-v1"}
        )
        self.assertEqual(duplicate_status, 200)
        self.assertFalse(duplicate["created"])
        self.assertEqual(duplicate["job"]["job_id"], self.job_id)

        with self.repository.database.connect() as conn:
            retry = conn.execute(
                "SELECT attempts,error_history_json FROM job_items WHERE tenant_id='demo' AND job_id=? AND target_kind='image' AND target_id='img-red-fox-04'",
                (self.job_id,),
            ).fetchone()
            tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertEqual(retry["attempts"], 2)
        self.assertIn("missing required fields", retry["error_history_json"])
        self.assertTrue({"image_tags", "image_embeddings", "post_embeddings", "suggestions", "reviews", "cost_ledger"}.issubset(tables))
        self.assertTrue({"idx_images_tenant_status", "idx_cost_tenant_created", "idx_suggestions_tenant_post"}.issubset(indexes))
        costs_status, costs = self.request("GET", "/costs?limit=1000")
        self.assertEqual(costs_status, 200)
        self.assertEqual(costs["total_calls"], 110)
        self.assertEqual(len(costs["entries"]), 110)

        images = self.repository.list_images("demo", ready_only=True)
        self.assertEqual(len(images), 48)
        self.assertEqual(sum(bool(image["review_required"]) for image in images), 1)
        self.assertTrue(all(image["tags"] is not None and image["embedding"] is not None for image in images))
        print(
            "ACCEPTANCE_PROOF batch "
            + json.dumps(
                {
                    "status": self.final_job["status"],
                    "completed_items": self.final_job["progress"]["completed_items"],
                    "failed_items": self.final_job["progress"]["failed_items"],
                    "retries": self.final_job["retries"],
                    "low_confidence_items": self.final_job["low_confidence_items"],
                    "low_confidence_image_ids": sorted(image["image_id"] for image in images if image["review_required"]),
                    "retry_error_history": retry["error_history_json"],
                    "vision_calls": self.final_job["cost_calls"]["vision"]["calls"],
                    "embedding_calls": self.final_job["cost_calls"]["embedding"]["calls"],
                    "cost_usd": self.final_job["cost_usd"],
                    "image_count": len(images),
                    "retry_attempts": retry["attempts"],
                    "cost_ledger_rows": costs["total_calls"],
                    "required_tables_present": sorted({"image_tags", "image_embeddings", "post_embeddings", "suggestions", "reviews", "cost_ledger"}.intersection(tables)),
                    "required_indexes_present": sorted({"idx_images_tenant_status", "idx_cost_tenant_created", "idx_suggestions_tenant_post"}.intersection(indexes)),
                    "idempotent_replay_status": duplicate_status,
                },
                sort_keys=True,
            )
        )

    def test_eval_precision_and_semantic_alias(self) -> None:
        evaluation = read_json(FIXTURE_DIR / "eval.json")
        result = evaluate_repository(self.repository, evaluation)
        self.assertEqual(result["total"], 12)
        self.assertEqual(result["correct"], 12)
        self.assertEqual(result["precision"], 1.0)
        status, fox = self.request("GET", "/posts/post-red-fox/images")
        self.assertEqual(status, 200)
        self.assertEqual(fox["status"], "matched")
        self.assertEqual(fox["suggested_image"]["image_id"], "img-red-fox-01")
        print(
            "ACCEPTANCE_PROOF matching "
            + json.dumps(
                {
                    "top1_correct": f"{result['correct']}/{result['total']} = {result['precision']:.3f}",
                    "red_fox_status": fox["status"],
                    "red_fox_image": fox["suggested_image"]["image_id"],
                    "alias": "Vulpes vulpes -> red fox",
                },
                sort_keys=True,
            )
        )

    def test_guard_refuses_forced_wolf_and_unknown_post(self) -> None:
        status, wolf = self.request("GET", "/posts/post-red-fox/images?candidate_id=img-gray-wolf-01")
        self.assertEqual(status, 200)
        self.assertEqual(wolf["status"], "rejected")
        wolf_reason = "; ".join(wolf["forced_candidate"]["reasons"])
        self.assertIn("Animal category mismatch", wolf_reason)
        self.assertIn("red fox", wolf_reason)
        self.assertIn("gray wolf", wolf_reason)

        status, no_match = self.request("GET", "/posts/post-no-match/images")
        self.assertEqual(status, 200)
        self.assertEqual(no_match["status"], "no_confident_match")
        self.assertIsNone(no_match["suggested_image"])
        self.assertTrue(no_match["reasons"])
        print(
            "ACCEPTANCE_PROOF mismatch_guard "
            + json.dumps(
                {
                    "forced_wolf_status": wolf["status"],
                    "forced_wolf_reason": wolf["forced_candidate"]["reasons"],
                    "unsupported_post_status": no_match["status"],
                    "unsupported_post_reasons": no_match["reasons"],
                },
                sort_keys=True,
            )
        )

    def test_review_flow_is_idempotent_and_guarded(self) -> None:
        status, created = self.request(
            "POST", "/posts/post-red-fox/suggestions", headers={"Idempotency-Key": "suggestion-run-v1"}
        )
        self.assertEqual(status, 201)
        self.assertTrue(created["created"])
        suggestion = created["suggested_image"]
        self.assertTrue(suggestion["accepted"])

        status, repeated = self.request(
            "POST", "/posts/post-red-fox/suggestions", headers={"Idempotency-Key": "suggestion-run-v1"}
        )
        self.assertEqual(status, 200)
        self.assertFalse(repeated["created"])
        self.assertEqual(repeated["run_id"], created["run_id"])

        headers = {"Idempotency-Key": "review-approve-v1"}
        status, review = self.request(
            "POST", f"/suggestions/{suggestion['suggestion_id']}/review", {"action": "approve", "note": "Reviewed fixture."}, headers
        )
        self.assertEqual(status, 201)
        self.assertEqual(review["review"]["action"], "approve")
        status, same_review = self.request(
            "POST", f"/suggestions/{suggestion['suggestion_id']}/review", {"action": "approve", "note": "Reviewed fixture."}, headers
        )
        self.assertEqual(status, 200)
        self.assertFalse(same_review["created"])

        rejected = next(item for item in created["suggestions"] if not item["accepted"])
        status, invalid_approval = self.request(
            "POST", f"/suggestions/{rejected['suggestion_id']}/review", {"action": "approve"}, {"Idempotency-Key": "review-wolf-v1"}
        )
        self.assertEqual(status, 409)
        self.assertEqual(invalid_approval["error"]["code"], "guard_rejected")
        print(
            "ACCEPTANCE_PROOF review "
            + json.dumps(
                {
                    "suggestion_create": 201,
                    "suggestion_replay": 200,
                    "review_action": review["review"]["action"],
                    "review_replay": 200,
                    "rejected_candidate_approval": status,
                },
                sort_keys=True,
            )
        )

    def test_input_errors_and_tenant_isolation_are_clean(self) -> None:
        status, missing_key = self.request("POST", "/jobs", {"kind": "process-corpus"})
        self.assertEqual(status, 400)
        self.assertEqual(missing_key["error"]["code"], "idempotency_key_required")

        status, invalid_json_shape = self.request("POST", "/jobs", ["not", "an", "object"], {"Idempotency-Key": "bad-shape"})  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertEqual(invalid_json_shape["error"]["code"], "invalid_body")

        status, invalid_action = self.request(
            "POST", "/suggestions/some-id/review", {"action": ["approve"]}, {"Idempotency-Key": "bad-action"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(invalid_action["error"]["code"], "invalid_review")

        status, other_tenant = self.request("GET", "/posts/post-red-fox/images", headers={"X-Tenant-ID": "tenant-other"})
        self.assertEqual(status, 404)
        self.assertEqual(other_tenant["error"]["code"], "post_not_found")

        status, other_job = self.request("GET", f"/jobs/{self.job_id}", headers={"X-Tenant-ID": "tenant-other"})
        self.assertEqual(status, 404)

        from image_relevance.api import openapi_document

        openapi = openapi_document()
        self.assertNotIn("security", openapi)
        self.assertNotIn("components", openapi)
        self.assertIn("not authentication or authorization", openapi["info"]["description"])
        print(
            "ACCEPTANCE_PROOF boundaries "
            + json.dumps(
                {
                    "missing_idempotency_key": missing_key["error"]["code"],
                    "non_object_json": invalid_json_shape["error"]["code"],
                    "invalid_action": invalid_action["error"]["code"],
                    "cross_tenant_post_status": 404,
                    "cross_tenant_post_error": other_tenant["error"]["code"],
                    "cross_tenant_job_status": 404,
                    "openapi_auth_security_declared": False,
                    "tenant_header_is_auth": False,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
