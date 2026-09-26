"""Tenant-scoped persistence. Every application query includes tenant_id."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .database import Database, utc_now


def _dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _load(value: str | None, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    return json.loads(value)


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_tenant(self, tenant_id: str) -> None:
        with self.database.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO tenants(tenant_id, created_at) VALUES (?, ?)", (tenant_id, utc_now()))

    def seed_corpus(self, tenant_id: str, corpus: dict[str, Any]) -> dict[str, int]:
        self.ensure_tenant(tenant_id)
        now = utc_now()
        image_count = 0
        post_count = 0
        with self.database.connect() as conn:
            for item in corpus["images"]:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO images(tenant_id,image_id,reference,fixture_json,invalid_first_attempts,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        tenant_id,
                        item["image_id"],
                        item["reference"],
                        _dump(item["vision_output"]),
                        int(item.get("invalid_first_attempts", 0)),
                        now,
                    ),
                )
                image_count += cursor.rowcount
            for item in corpus["posts"]:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO posts(tenant_id,post_id,title,body,created_at) VALUES (?,?,?,?,?)",
                    (tenant_id, item["post_id"], item["title"], item["body"], now),
                )
                post_count += cursor.rowcount
        return {"images_inserted": image_count, "posts_inserted": post_count}

    def image_fixture(self, tenant_id: str, image_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT image_id,reference,fixture_json,invalid_first_attempts FROM images WHERE tenant_id=? AND image_id=?",
                (tenant_id, image_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "image_id": row["image_id"],
            "reference": row["reference"],
            "vision_output": _load(row["fixture_json"], {}),
            "invalid_first_attempts": row["invalid_first_attempts"],
        }

    def mark_image_failed(self, tenant_id: str, image_id: str) -> None:
        with self.database.connect() as conn:
            conn.execute("UPDATE images SET tag_status='failed' WHERE tenant_id=? AND image_id=?", (tenant_id, image_id))

    def list_images(self, tenant_id: str, ready_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE i.tenant_id=?" + (" AND i.tag_status IN ('ready','review_required')" if ready_only else "")
        with self.database.connect() as conn:
            rows = conn.execute(
                f"""SELECT i.image_id,i.reference,i.tag_status,t.payload_json,t.review_required,t.confidence,
                           e.model_id,e.vector_json
                    FROM images i
                    LEFT JOIN image_tags t ON t.tenant_id=i.tenant_id AND t.image_id=i.image_id
                    LEFT JOIN image_embeddings e ON e.tenant_id=i.tenant_id AND e.image_id=i.image_id
                    {where} ORDER BY i.image_id""",
                (tenant_id,),
            ).fetchall()
        return [self._image_from_row(row) for row in rows]

    def get_image(self, tenant_id: str, image_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """SELECT i.image_id,i.reference,i.tag_status,t.payload_json,t.review_required,t.confidence,
                          e.model_id,e.vector_json
                   FROM images i LEFT JOIN image_tags t ON t.tenant_id=i.tenant_id AND t.image_id=i.image_id
                   LEFT JOIN image_embeddings e ON e.tenant_id=i.tenant_id AND e.image_id=i.image_id
                   WHERE i.tenant_id=? AND i.image_id=?""",
                (tenant_id, image_id),
            ).fetchone()
        return None if row is None else self._image_from_row(row)

    @staticmethod
    def _image_from_row(row: Any) -> dict[str, Any]:
        return {
            "image_id": row["image_id"],
            "reference": row["reference"],
            "tag_status": row["tag_status"],
            "tags": _load(row["payload_json"]),
            "review_required": bool(row["review_required"]) if row["review_required"] is not None else None,
            "confidence": row["confidence"],
            "model_id": row["model_id"],
            "embedding": _load(row["vector_json"]),
        }

    def list_posts(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """SELECT p.post_id,p.title,p.body,e.model_id,e.vector_json
                   FROM posts p LEFT JOIN post_embeddings e ON e.tenant_id=p.tenant_id AND e.post_id=p.post_id
                   WHERE p.tenant_id=? ORDER BY p.post_id""",
                (tenant_id,),
            ).fetchall()
        return [self._post_from_row(row) for row in rows]

    def get_post(self, tenant_id: str, post_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """SELECT p.post_id,p.title,p.body,e.model_id,e.vector_json
                   FROM posts p LEFT JOIN post_embeddings e ON e.tenant_id=p.tenant_id AND e.post_id=p.post_id
                   WHERE p.tenant_id=? AND p.post_id=?""",
                (tenant_id, post_id),
            ).fetchone()
        return None if row is None else self._post_from_row(row)

    @staticmethod
    def _post_from_row(row: Any) -> dict[str, Any]:
        return {
            "post_id": row["post_id"],
            "title": row["title"],
            "body": row["body"],
            "model_id": row["model_id"],
            "embedding": _load(row["vector_json"]),
        }

    def save_image_tags(self, tenant_id: str, image_id: str, tags: dict[str, Any], review_required: bool) -> None:
        now = utc_now()
        with self.database.connect() as conn:
            conn.execute(
                """INSERT INTO image_tags(tenant_id,image_id,schema_version,payload_json,confidence,review_required,updated_at)
                   VALUES (?,?,1,?,?,?,?)
                   ON CONFLICT(tenant_id,image_id) DO UPDATE SET schema_version=excluded.schema_version,
                   payload_json=excluded.payload_json,confidence=excluded.confidence,
                   review_required=excluded.review_required,updated_at=excluded.updated_at""",
                (tenant_id, image_id, _dump(tags), tags["confidence"], int(review_required), now),
            )
            conn.execute(
                "UPDATE images SET tag_status=? WHERE tenant_id=? AND image_id=?",
                ("review_required" if review_required else "ready", tenant_id, image_id),
            )

    def save_image_embedding(self, tenant_id: str, image_id: str, model_id: str, vector: list[float]) -> None:
        with self.database.connect() as conn:
            conn.execute(
                """INSERT INTO image_embeddings(tenant_id,image_id,model_id,dimensions,vector_json,updated_at)
                   VALUES (?,?,?,?,?,?) ON CONFLICT(tenant_id,image_id) DO UPDATE SET model_id=excluded.model_id,
                   dimensions=excluded.dimensions,vector_json=excluded.vector_json,updated_at=excluded.updated_at""",
                (tenant_id, image_id, model_id, len(vector), _dump(vector), utc_now()),
            )

    def save_post_embedding(self, tenant_id: str, post_id: str, model_id: str, vector: list[float]) -> None:
        with self.database.connect() as conn:
            conn.execute(
                """INSERT INTO post_embeddings(tenant_id,post_id,model_id,dimensions,vector_json,updated_at)
                   VALUES (?,?,?,?,?,?) ON CONFLICT(tenant_id,post_id) DO UPDATE SET model_id=excluded.model_id,
                   dimensions=excluded.dimensions,vector_json=excluded.vector_json,updated_at=excluded.updated_at""",
                (tenant_id, post_id, model_id, len(vector), _dump(vector), utc_now()),
            )

    def create_job(self, tenant_id: str, idempotency_key: str) -> tuple[dict[str, Any], bool]:
        self.ensure_tenant(tenant_id)
        with self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM jobs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)
            ).fetchone()
            if existing:
                conn.commit()
                return self.get_job(tenant_id, existing["job_id"]), False  # type: ignore[return-value]
            images = conn.execute("SELECT image_id FROM images WHERE tenant_id=? ORDER BY image_id", (tenant_id,)).fetchall()
            posts = conn.execute("SELECT post_id FROM posts WHERE tenant_id=? ORDER BY post_id", (tenant_id,)).fetchall()
            job_id = f"job_{uuid.uuid4().hex[:16]}"
            total = len(images) + len(posts)
            now = utc_now()
            conn.execute(
                "INSERT INTO jobs(job_id,tenant_id,idempotency_key,kind,status,total_items,created_at) VALUES (?,?,?,'process-corpus','pending',?,?)",
                (job_id, tenant_id, idempotency_key, total, now),
            )
            conn.executemany(
                "INSERT INTO job_items(tenant_id,job_id,target_kind,target_id,status,updated_at) VALUES (?,?,'image',?,'pending',?)",
                [(tenant_id, job_id, row["image_id"], now) for row in images],
            )
            conn.executemany(
                "INSERT INTO job_items(tenant_id,job_id,target_kind,target_id,status,updated_at) VALUES (?,?,'post',?,'pending',?)",
                [(tenant_id, job_id, row["post_id"], now) for row in posts],
            )
            conn.commit()
        return self.get_job(tenant_id, job_id), True  # type: ignore[return-value]

    def set_job_running(self, tenant_id: str, job_id: str) -> None:
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='running',started_at=COALESCE(started_at,?) WHERE tenant_id=? AND job_id=? AND status IN ('pending','running')",
                (utc_now(), tenant_id, job_id),
            )

    def pending_job_items(self, tenant_id: str, job_id: str) -> list[dict[str, str]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                "SELECT target_kind,target_id FROM job_items WHERE tenant_id=? AND job_id=? AND status IN ('pending','running') ORDER BY target_kind,target_id",
                (tenant_id, job_id),
            ).fetchall()
        return [{"target_kind": row["target_kind"], "target_id": row["target_id"]} for row in rows]

    def begin_attempt(self, tenant_id: str, job_id: str, target_kind: str, target_id: str) -> int:
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE job_items SET status='running',attempts=attempts+1,updated_at=? WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (utc_now(), tenant_id, job_id, target_kind, target_id),
            )
            row = conn.execute(
                "SELECT attempts FROM job_items WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (tenant_id, job_id, target_kind, target_id),
            ).fetchone()
            attempts = int(row["attempts"])
            if attempts > 1:
                conn.execute("UPDATE jobs SET retries=retries+1 WHERE tenant_id=? AND job_id=?", (tenant_id, job_id))
        return attempts

    def item_attempts(self, tenant_id: str, job_id: str, target_kind: str, target_id: str) -> int:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM job_items WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (tenant_id, job_id, target_kind, target_id),
            ).fetchone()
        return int(row["attempts"]) if row else 0

    def add_item_error(self, tenant_id: str, job_id: str, target_kind: str, target_id: str, error: str) -> None:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT error_history_json FROM job_items WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (tenant_id, job_id, target_kind, target_id),
            ).fetchone()
            history = _load(row["error_history_json"], []) if row else []
            history.append(error[:240])
            conn.execute(
                "UPDATE job_items SET error_history_json=?,updated_at=? WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (_dump(history), utc_now(), tenant_id, job_id, target_kind, target_id),
            )

    def finish_item(
        self,
        tenant_id: str,
        job_id: str,
        target_kind: str,
        target_id: str,
        status: str,
        low_confidence: bool = False,
        error: str | None = None,
    ) -> None:
        if status not in {"completed", "failed"}:
            raise ValueError("item status must be completed or failed")
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT status FROM job_items WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (tenant_id, job_id, target_kind, target_id),
            ).fetchone()
            if row is None or row["status"] in {"completed", "failed"}:
                return
            conn.execute(
                "UPDATE job_items SET status=?,updated_at=? WHERE tenant_id=? AND job_id=? AND target_kind=? AND target_id=?",
                (status, utc_now(), tenant_id, job_id, target_kind, target_id),
            )
            if status == "completed":
                conn.execute(
                    "UPDATE jobs SET completed_items=completed_items+1,low_confidence_items=low_confidence_items+? WHERE tenant_id=? AND job_id=?",
                    (int(low_confidence), tenant_id, job_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET failed_items=failed_items+1,last_error=? WHERE tenant_id=? AND job_id=?",
                    ((error or "item failed")[:400], tenant_id, job_id),
                )

    def record_cost(
        self,
        tenant_id: str,
        job_id: str,
        target_kind: str,
        target_id: str,
        call_kind: str,
        provider: str,
        model_id: str,
        attempt: int,
        units: int,
        cost_usd: float,
    ) -> None:
        with self.database.connect() as conn:
            conn.execute(
                """INSERT INTO cost_ledger(call_id,tenant_id,job_id,target_kind,target_id,call_kind,provider,model_id,attempt,units,cost_usd,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"call_{uuid.uuid4().hex}", tenant_id, job_id, target_kind, target_id, call_kind, provider, model_id, attempt, units, cost_usd, utc_now()),
            )
            conn.execute("UPDATE jobs SET cost_usd=cost_usd+? WHERE tenant_id=? AND job_id=?", (cost_usd, tenant_id, job_id))

    def finish_job(self, tenant_id: str, job_id: str, fatal_error: str | None = None) -> None:
        with self.database.connect() as conn:
            row = conn.execute("SELECT failed_items FROM jobs WHERE tenant_id=? AND job_id=?", (tenant_id, job_id)).fetchone()
            if row is None:
                return
            if fatal_error:
                status = "failed"
                error = fatal_error[:400]
            else:
                status = "completed_with_warnings" if row["failed_items"] else "completed"
                error = None
            conn.execute(
                "UPDATE jobs SET status=?,last_error=COALESCE(?,last_error),finished_at=? WHERE tenant_id=? AND job_id=?",
                (status, error, utc_now(), tenant_id, job_id),
            )

    def get_job(self, tenant_id: str, job_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE tenant_id=? AND job_id=?", (tenant_id, job_id)).fetchone()
            if row is None:
                return None
            call_rows = conn.execute(
                "SELECT call_kind,COUNT(*) AS calls,COALESCE(SUM(cost_usd),0) AS cost_usd FROM cost_ledger WHERE tenant_id=? AND job_id=? GROUP BY call_kind",
                (tenant_id, job_id),
            ).fetchall()
        processed = row["completed_items"] + row["failed_items"]
        progress = 100 if row["total_items"] == 0 else round(100 * processed / row["total_items"], 1)
        return {
            "job_id": row["job_id"],
            "tenant_id": row["tenant_id"],
            "kind": row["kind"],
            "status": row["status"],
            "progress": {
                "completed_items": row["completed_items"],
                "failed_items": row["failed_items"],
                "total_items": row["total_items"],
                "percent": progress,
            },
            "retries": row["retries"],
            "low_confidence_items": row["low_confidence_items"],
            "cost_usd": round(row["cost_usd"], 8),
            "cost_calls": {item["call_kind"]: {"calls": item["calls"], "cost_usd": round(item["cost_usd"], 8)} for item in call_rows},
            "last_error": row["last_error"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    def list_jobs(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute("SELECT job_id FROM jobs WHERE tenant_id=? ORDER BY created_at DESC", (tenant_id,)).fetchall()
        return [job for row in rows if (job := self.get_job(tenant_id, row["job_id"])) is not None]

    def list_incomplete_jobs(self) -> list[dict[str, str]]:
        with self.database.connect() as conn:
            rows = conn.execute("SELECT tenant_id,job_id FROM jobs WHERE status IN ('pending','running') ORDER BY created_at").fetchall()
        return [{"tenant_id": row["tenant_id"], "job_id": row["job_id"]} for row in rows]

    def list_costs(self, tenant_id: str, limit: int = 200) -> dict[str, Any]:
        with self.database.connect() as conn:
            rows = conn.execute(
                "SELECT call_id,job_id,target_kind,target_id,call_kind,provider,model_id,attempt,units,cost_usd,created_at FROM cost_ledger WHERE tenant_id=? ORDER BY created_at DESC,call_id LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) AS count,COALESCE(SUM(cost_usd),0) AS cost FROM cost_ledger WHERE tenant_id=?", (tenant_id,)).fetchone()
        return {
            "tenant_id": tenant_id,
            "total_calls": total["count"],
            "total_cost_usd": round(total["cost"], 8),
            "entries": [dict(row) for row in rows],
        }

    def create_suggestion_run(
        self,
        tenant_id: str,
        post_id: str,
        idempotency_key: str,
        ranked: list[dict[str, Any]],
    ) -> tuple[str, bool]:
        with self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT run_id,post_id FROM suggestion_runs WHERE tenant_id=? AND idempotency_key=?",
                (tenant_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["post_id"] != post_id:
                    conn.rollback()
                    raise ValueError("Idempotency-Key was already used for a different post")
                conn.commit()
                return existing["run_id"], False
            run_id = f"run_{uuid.uuid4().hex[:16]}"
            conn.execute(
                "INSERT INTO suggestion_runs(run_id,tenant_id,post_id,idempotency_key,created_at) VALUES (?,?,?,?,?)",
                (run_id, tenant_id, post_id, idempotency_key, utc_now()),
            )
            conn.executemany(
                """INSERT INTO suggestions(suggestion_id,tenant_id,run_id,post_id,image_id,similarity,accepted,reasons_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        f"sug_{uuid.uuid4().hex[:16]}",
                        tenant_id,
                        run_id,
                        post_id,
                        item["image_id"],
                        item["similarity"],
                        int(bool(item["accepted"])),
                        _dump(item["reasons"]),
                        utc_now(),
                    )
                    for item in ranked
                ],
            )
            conn.commit()
        return run_id, True

    def list_suggestions(self, tenant_id: str, post_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """SELECT s.suggestion_id,s.run_id,s.post_id,s.image_id,s.similarity,s.accepted,s.reasons_json,s.created_at,
                          i.reference,t.payload_json
                   FROM suggestions s JOIN images i ON i.tenant_id=s.tenant_id AND i.image_id=s.image_id
                   LEFT JOIN image_tags t ON t.tenant_id=s.tenant_id AND t.image_id=s.image_id
                   WHERE s.tenant_id=? AND s.post_id=? ORDER BY s.created_at DESC,s.similarity DESC""",
                (tenant_id, post_id),
            ).fetchall()
        return [
            {
                "suggestion_id": row["suggestion_id"],
                "run_id": row["run_id"],
                "post_id": row["post_id"],
                "image_id": row["image_id"],
                "reference": row["reference"],
                "tags": _load(row["payload_json"]),
                "similarity": row["similarity"],
                "accepted": bool(row["accepted"]),
                "reasons": _load(row["reasons_json"], []),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_suggestion(self, tenant_id: str, suggestion_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """SELECT s.suggestion_id,s.run_id,s.post_id,s.image_id,s.similarity,s.accepted,s.reasons_json,s.created_at,
                          i.reference,t.payload_json
                   FROM suggestions s JOIN images i ON i.tenant_id=s.tenant_id AND i.image_id=s.image_id
                   LEFT JOIN image_tags t ON t.tenant_id=s.tenant_id AND t.image_id=s.image_id
                   WHERE s.tenant_id=? AND s.suggestion_id=?""",
                (tenant_id, suggestion_id),
            ).fetchone()
            if row is None:
                return None
            reviews = conn.execute(
                "SELECT action,note,created_at FROM reviews WHERE tenant_id=? AND suggestion_id=? ORDER BY created_at DESC",
                (tenant_id, suggestion_id),
            ).fetchall()
        return {
            "suggestion_id": row["suggestion_id"],
            "run_id": row["run_id"],
            "post_id": row["post_id"],
            "image_id": row["image_id"],
            "reference": row["reference"],
            "tags": _load(row["payload_json"]),
            "similarity": row["similarity"],
            "accepted": bool(row["accepted"]),
            "reasons": _load(row["reasons_json"], []),
            "created_at": row["created_at"],
            "reviews": [dict(review) for review in reviews],
        }

    def create_review(
        self,
        tenant_id: str,
        suggestion_id: str,
        action: str,
        note: str,
        idempotency_key: str,
    ) -> tuple[dict[str, Any], bool]:
        with self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM reviews WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)
            ).fetchone()
            if existing:
                same = (
                    existing["suggestion_id"] == suggestion_id
                    and existing["action"] == action
                    and existing["note"] == note
                )
                conn.commit()
                if not same:
                    raise ValueError("Idempotency-Key was already used for a different review")
                return dict(existing), False
            review_id = f"rev_{uuid.uuid4().hex[:16]}"
            conn.execute(
                "INSERT INTO reviews(review_id,tenant_id,suggestion_id,action,note,idempotency_key,created_at) VALUES (?,?,?,?,?,?,?)",
                (review_id, tenant_id, suggestion_id, action, note, idempotency_key, utc_now()),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM reviews WHERE tenant_id=? AND review_id=?", (tenant_id, review_id)).fetchone()
        return dict(row), True
