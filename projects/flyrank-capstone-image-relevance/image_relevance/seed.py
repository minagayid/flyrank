"""Load the synthetic corpus without overwriting tenant-owned records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH
from .database import Database
from .repository import Repository


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def seed_demo(database_path: str | Path = DATABASE_PATH, tenant_id: str = "demo") -> dict[str, int]:
    database = Database(database_path)
    database.initialize()
    repository = Repository(database)
    result = repository.seed_corpus(tenant_id, read_json(FIXTURE_DIR / "corpus.json"))
    return result


def main() -> None:
    counts = seed_demo()
    print(f"Seeded demo tenant: {counts['images_inserted']} images, {counts['posts_inserted']} posts added.")
    print("Existing rows were preserved; the seed step is safe to repeat.")


if __name__ == "__main__":
    main()
