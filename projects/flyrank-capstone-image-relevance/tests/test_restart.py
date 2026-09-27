from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from image_relevance.database import Database
from image_relevance.jobs import JobManager
from image_relevance.repository import Repository
from image_relevance.seed import FIXTURE_DIR, read_json


class RestartRecoveryTests(unittest.TestCase):
    def test_running_job_resumes_from_persisted_attempt_count(self) -> None:
        with tempfile.TemporaryDirectory(prefix="image-relevance-restart-") as temp_dir:
            database = Database(Path(temp_dir) / "restart.sqlite3")
            database.initialize()
            repository = Repository(database)
            full_corpus = read_json(FIXTURE_DIR / "corpus.json")
            corpus = {**full_corpus, "images": full_corpus["images"][:1], "posts": full_corpus["posts"][:1]}
            repository.seed_corpus("demo", corpus)
            job, created = repository.create_job("demo", "restart-v1")
            self.assertTrue(created)
            repository.set_job_running("demo", job["job_id"])
            attempt = repository.begin_attempt("demo", job["job_id"], "image", "img-red-fox-01")
            repository.record_cost("demo", job["job_id"], "image", "img-red-fox-01", "vision", "mock-vision", "fixture-vision-v1", attempt, 1, 0.0)
            repository.add_item_error("demo", job["job_id"], "image", "img-red-fox-01", "simulated interruption after attempt one")

            resumed = JobManager(repository, max_retries=2)
            resumed.resume_incomplete_jobs()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = repository.get_job("demo", job["job_id"])
                if result["status"] not in {"pending", "running"}:
                    break
                time.sleep(0.02)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["progress"]["completed_items"], 2)
            self.assertEqual(result["retries"], 1)
            self.assertEqual(repository.item_attempts("demo", job["job_id"], "image", "img-red-fox-01"), 2)
            self.assertEqual(repository.list_costs("demo")["total_calls"], 4)
            print(
                "ACCEPTANCE_PROOF restart "
                + json.dumps(
                    {
                        "status": result["status"],
                        "completed_items": result["progress"]["completed_items"],
                        "retries": result["retries"],
                        "image_attempts": repository.item_attempts("demo", job["job_id"], "image", "img-red-fox-01"),
                        "ledger_calls": repository.list_costs("demo")["total_calls"],
                    },
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
