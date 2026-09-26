from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from image_relevance.database import Database
from image_relevance.jobs import JobManager
from image_relevance.repository import Repository
from image_relevance.seed import FIXTURE_DIR, read_json


class BudgetGuardTests(unittest.TestCase):
    def test_estimated_cost_over_budget_blocks_the_first_provider_call(self) -> None:
        with tempfile.TemporaryDirectory(prefix="image-relevance-budget-") as temp_dir:
            database = Database(Path(temp_dir) / "budget.sqlite3")
            database.initialize()
            repository = Repository(database)
            repository.seed_corpus("demo", read_json(FIXTURE_DIR / "corpus.json"))
            job, created = repository.create_job("demo", "budget-guard-v1")
            self.assertTrue(created)

            manager = JobManager(
                repository,
                confidence_threshold=0.70,
                cost_budget_usd=0.001,
                max_retries=2,
                call_cost_usd={"vision": 0.01},
            )
            with self.assertLogs("image_relevance.jobs", level="ERROR") as captured:
                manager.run("demo", job["job_id"])

            result = repository.get_job("demo", job["job_id"])
            costs = repository.list_costs("demo")
            self.assertEqual(result["status"], "failed")
            self.assertIn("exceed the 0.0010 USD job budget", result["last_error"])
            self.assertEqual(result["progress"]["failed_items"], 1)
            self.assertEqual(costs["total_calls"], 0)
            self.assertTrue(any("ALERT batch processing failed" in item for item in captured.output))
            print(
                "ACCEPTANCE_PROOF budget_failure "
                + json.dumps(
                    {
                        "job_status": result["status"],
                        "failed_items": result["progress"]["failed_items"],
                        "ledger_calls": costs["total_calls"],
                        "alert": captured.output[0],
                    },
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
