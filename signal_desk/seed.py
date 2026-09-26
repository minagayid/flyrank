from __future__ import annotations

import os

from signal_desk.config import DEMO_USER
from signal_desk.database import initialize, reader
from signal_desk.leads import create_lead
from signal_desk.security import create_user

DEMO_LEADS = [
    {
        "full_name": "Alex Example",
        "email": "alex@example.invalid",
        "company": "North Star Studio",
        "project_description": "We need a visual identity and logo refresh for a small neighborhood bakery.",
        "budget_range": "",
        "timeline": "next month",
    },
    {
        "full_name": "Jordan Sample",
        "email": "jordan@example.invalid",
        "company": "Field Notes Co.",
        "project_description": "Please help us design a campaign landing website and product visuals. The launch is urgent, by next week.",
        "budget_range": "$4,000–$6,000",
        "timeline": "next week",
    },
    {
        "full_name": "Riley Fiction",
        "email": "riley@example.invalid",
        "company": "",
        "project_description": "I am exploring a design project and would like to discuss possible deliverables.",
        "budget_range": "",
        "timeline": "",
    },
]


def seed() -> int:
    password = os.environ.get("SIGNAL_DESK_DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit(
            "Set SIGNAL_DESK_DEMO_PASSWORD to a local password of at least 12 characters, then rerun the seed command."
        )
    initialize()
    with reader() as connection:
        row = connection.execute("SELECT id FROM users WHERE username=?", (DEMO_USER,)).fetchone()
    if row is None:
        create_user(DEMO_USER, password)
        with reader() as connection:
            row = connection.execute("SELECT id FROM users WHERE username=?", (DEMO_USER,)).fetchone()
    user_id = row["id"]
    inserted = 0
    for lead in DEMO_LEADS:
        with reader() as connection:
            exists = connection.execute(
                "SELECT 1 FROM leads WHERE user_id=? AND email=?", (user_id, lead["email"])
            ).fetchone()
        if not exists:
            create_lead(user_id, lead)
            inserted += 1
    return inserted


def main() -> None:
    inserted = seed()
    print(f"Seed complete: {inserted} fictional demo lead(s) added or already present.")
    print("The demo account password was not displayed. Keep the chosen password outside source control.")


if __name__ == "__main__":
    main()
