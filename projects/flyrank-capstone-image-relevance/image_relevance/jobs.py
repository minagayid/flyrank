"""Asynchronous corpus processing with bounded retries and per-call cost rows."""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any

from .embeddings import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, create_embedder, image_embedding_text
from .repository import Repository
from .schema import SchemaValidationError, validate_vision_output


VISION_PROVIDER = "mock-vision"
VISION_MODEL = "fixture-vision-v1"
logger = logging.getLogger("image_relevance.jobs")


class BudgetExceeded(RuntimeError):
    pass


class JobManager:
    def __init__(
        self,
        repository: Repository,
        confidence_threshold: float = 0.70,
        cost_budget_usd: float = 0.10,
        max_retries: int = 2,
        call_cost_usd: dict[str, float] | None = None,
        embedding_provider: str = "hash",
        ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
        ollama_model: str = DEFAULT_OLLAMA_MODEL,
        ollama_timeout_seconds: float = 30.0,
    ) -> None:
        self.repository = repository
        self.confidence_threshold = confidence_threshold
        self.cost_budget_usd = cost_budget_usd
        self.max_retries = max_retries
        self.call_cost_usd = {"vision": 0.0, "embedding": 0.0}
        if call_cost_usd:
            self.call_cost_usd.update(call_cost_usd)
        if any(value < 0 for value in self.call_cost_usd.values()):
            raise ValueError("per-call costs must be non-negative")
        self.embedder = create_embedder(
            embedding_provider,
            model_id=ollama_model,
            base_url=ollama_base_url,
            timeout_seconds=ollama_timeout_seconds,
        )
        self._lock = threading.Lock()
        self._active: set[str] = set()

    @staticmethod
    def _alert(job_id: str, target_kind: str, error_code: str) -> None:
        # Do not include input text, provider error bodies, or secrets in alerts.
        logger.error(
            "ALERT batch processing failed job_id=%s target_kind=%s error_code=%s",
            job_id,
            target_kind,
            error_code,
        )

    def submit(self, tenant_id: str, idempotency_key: str) -> tuple[dict[str, Any], bool]:
        job, created = self.repository.create_job(tenant_id, idempotency_key)
        if created:
            self.launch(tenant_id, job["job_id"])
        return job, created

    def launch(self, tenant_id: str, job_id: str) -> bool:
        with self._lock:
            if job_id in self._active:
                return False
            self._active.add(job_id)
        thread = threading.Thread(target=self._run_and_release, args=(tenant_id, job_id), daemon=True, name=f"batch-{job_id}")
        thread.start()
        return True

    def resume_incomplete_jobs(self) -> None:
        for item in self.repository.list_incomplete_jobs():
            self.launch(item["tenant_id"], item["job_id"])

    def _run_and_release(self, tenant_id: str, job_id: str) -> None:
        try:
            self.run(tenant_id, job_id)
        finally:
            with self._lock:
                self._active.discard(job_id)

    def _assert_budget(self, tenant_id: str, job_id: str, estimate: float) -> None:
        job = self.repository.get_job(tenant_id, job_id)
        spent = float(job["cost_usd"]) if job else 0.0
        if spent + estimate > self.cost_budget_usd:
            raise BudgetExceeded(
                f"Projected call cost would exceed the {self.cost_budget_usd:.4f} USD job budget"
            )

    def run(self, tenant_id: str, job_id: str) -> None:
        self.repository.set_job_running(tenant_id, job_id)
        try:
            for item in self.repository.pending_job_items(tenant_id, job_id):
                try:
                    if item["target_kind"] == "image":
                        self._process_image(tenant_id, job_id, item["target_id"])
                    else:
                        self._process_post(tenant_id, job_id, item["target_id"])
                except Exception as exc:
                    self.repository.finish_item(
                        tenant_id, job_id, item["target_kind"], item["target_id"], "failed", error=f"{type(exc).__name__}: {exc}"
                    )
                    raise
            self.repository.finish_job(tenant_id, job_id)
        except Exception as exc:  # Fatal job errors are persisted for an operator to inspect.
            self.repository.finish_job(tenant_id, job_id, f"{type(exc).__name__}: {exc}")
            self._alert(job_id, "job", type(exc).__name__)

    def _process_image(self, tenant_id: str, job_id: str, image_id: str) -> None:
        fixture = self.repository.image_fixture(tenant_id, image_id)
        if fixture is None:
            self.repository.finish_item(tenant_id, job_id, "image", image_id, "failed", error="image fixture is missing")
            self._alert(job_id, "image", "fixture_missing")
            return
        last_error = "vision attempt failed"
        remaining_attempts = max(0, self.max_retries + 1 - self.repository.item_attempts(tenant_id, job_id, "image", image_id))
        for _ in range(remaining_attempts):
            attempt = self.repository.begin_attempt(tenant_id, job_id, "image", image_id)
            self._assert_budget(tenant_id, job_id, self.call_cost_usd["vision"])
            payload = copy.deepcopy(fixture["vision_output"])
            if attempt <= int(fixture["invalid_first_attempts"]):
                payload.pop("caption", None)
            # The cost row is recorded for every request, including invalid output and retries.
            self.repository.record_cost(
                tenant_id, job_id, "image", image_id, "vision", VISION_PROVIDER, VISION_MODEL, attempt, 1, self.call_cost_usd["vision"]
            )
            try:
                tags = validate_vision_output(payload).to_dict()
            except SchemaValidationError as exc:
                last_error = str(exc)
                self.repository.add_item_error(tenant_id, job_id, "image", image_id, last_error)
                continue
            self.repository.save_image_tags(
                tenant_id, image_id, tags, float(tags["confidence"]) < self.confidence_threshold
            )
            try:
                self._assert_budget(tenant_id, job_id, self.call_cost_usd["embedding"])
                self.repository.record_cost(
                    tenant_id,
                    job_id,
                    "image",
                    image_id,
                    "embedding",
                    self.embedder.provider,
                    self.embedder.model_id,
                    attempt,
                    1,
                    self.call_cost_usd["embedding"],
                )
                vector = self.embedder.embed(image_embedding_text(tags))
                self.repository.save_image_embedding(tenant_id, image_id, self.embedder.model_id, vector)
            except BudgetExceeded:
                raise
            except Exception as exc:
                last_error = f"embedding failed: {exc}"
                self.repository.add_item_error(tenant_id, job_id, "image", image_id, last_error)
                continue
            self.repository.finish_item(
                tenant_id,
                job_id,
                "image",
                image_id,
                "completed",
                low_confidence=float(tags["confidence"]) < self.confidence_threshold,
            )
            return
        self.repository.mark_image_failed(tenant_id, image_id)
        self.repository.finish_item(tenant_id, job_id, "image", image_id, "failed", error=last_error)
        self._alert(job_id, "image", "retries_exhausted")

    def _process_post(self, tenant_id: str, job_id: str, post_id: str) -> None:
        post = self.repository.get_post(tenant_id, post_id)
        if post is None:
            self.repository.finish_item(tenant_id, job_id, "post", post_id, "failed", error="post is missing")
            self._alert(job_id, "post", "post_missing")
            return
        last_error = "embedding attempt failed"
        remaining_attempts = max(0, self.max_retries + 1 - self.repository.item_attempts(tenant_id, job_id, "post", post_id))
        for _ in range(remaining_attempts):
            attempt = self.repository.begin_attempt(tenant_id, job_id, "post", post_id)
            try:
                self._assert_budget(tenant_id, job_id, self.call_cost_usd["embedding"])
                self.repository.record_cost(
                    tenant_id,
                    job_id,
                    "post",
                    post_id,
                    "embedding",
                    self.embedder.provider,
                    self.embedder.model_id,
                    attempt,
                    1,
                    self.call_cost_usd["embedding"],
                )
                vector = self.embedder.embed(f"{post['title']} {post['body']}")
                self.repository.save_post_embedding(tenant_id, post_id, self.embedder.model_id, vector)
                self.repository.finish_item(tenant_id, job_id, "post", post_id, "completed")
                return
            except BudgetExceeded:
                raise
            except Exception as exc:
                last_error = f"embedding failed: {exc}"
                self.repository.add_item_error(tenant_id, job_id, "post", post_id, last_error)
        self.repository.finish_item(tenant_id, job_id, "post", post_id, "failed", error=last_error)
        self._alert(job_id, "post", "retries_exhausted")
