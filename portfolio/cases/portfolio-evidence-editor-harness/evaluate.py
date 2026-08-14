"""Run the public Portfolio Evidence Editor evaluation harness.

The v2 evaluator mirrors the small deterministic rules in agent/index.html. The
baseline is intentionally explicit: a formatter-only comparison that parses the
same labels but has no claim audit or empty-input refusal. This script evaluates
behavioral guardrails; it cannot decide whether a supplied claim is true or safe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


LABELS = ("Problem", "Role", "Method", "Evidence", "Limitation", "Next step")
RISKY_TERMS = ("guarantee", "proved", "always", "best", "perfect", "caused", "predicts google")
SIGNAL_LABELS = {
    "complete_input": "Complete labeled input",
    "missing_section": "Missing-section detection",
    "risky_language": "Risky-language detection",
    "numeric_audit": "Numeric-token audit",
    "empty_refusal": "Empty-input refusal",
}


def load_cases() -> list[dict]:
    path = Path(__file__).with_name("test-set.json")
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for line in text.splitlines():
        for label in LABELS:
            prefix = f"{label}:"
            if line.lower().startswith(prefix.lower()):
                sections[label] = line[len(prefix) :].strip()
                break
    return sections


def numeric_tokens(text: str) -> list[str]:
    # Keep the browser's /\b\d+(?:\.\d+)?%?\b/g behavior, including its
    # fallback to the numeric portion when a trailing percent sign has no word boundary.
    return re.findall(r"\b\d+(?:\.\d+)?%?\b", text)


def v2_evaluate(text: str) -> dict:
    if not text.strip():
        return {
            "status": "REFUSED_EMPTY",
            "missing_sections": [],
            "risk_terms": [],
            "numeric_tokens": [],
        }

    sections = parse_sections(text)
    risks = [term for term in RISKY_TERMS if term in text.lower()]
    return {
        "status": "REVISE BEFORE PUBLISHING" if risks else "READY FOR HUMAN FACT-CHECK",
        "missing_sections": [label for label in LABELS if label not in sections],
        "risk_terms": risks,
        "numeric_tokens": numeric_tokens(text),
    }


def baseline_evaluate(text: str) -> dict:
    """Formatter-only baseline used for the comparison column."""

    if not text.strip():
        return {"status": "DRAFTED", "missing_sections": [], "risk_terms": [], "numeric_tokens": []}
    parse_sections(text)
    return {"status": "READY FOR HUMAN FACT-CHECK", "missing_sections": [], "risk_terms": [], "numeric_tokens": []}


def matches_expected(actual: dict, expected: dict) -> bool:
    return all(actual[key] == expected[key] for key in ("status", "missing_sections", "risk_terms", "numeric_tokens"))


def score(cases: list[dict]) -> list[tuple[str, int, int, int, int]]:
    rows = []
    for signal, label in SIGNAL_LABELS.items():
        selected = [case for case in cases if signal in case["signals"]]
        v2_pass = sum(matches_expected(v2_evaluate(case["notes"]), case["expected"]) for case in selected)
        # The formatter-only baseline intentionally supports only the existence of
        # a complete labeled input; it has no implementation for the other signals.
        baseline_pass = sum(
            signal == "complete_input"
            and not baseline_evaluate(case["notes"])["missing_sections"]
            and bool(case["notes"].strip())
            for case in selected
        )
        rows.append((label, baseline_pass, len(selected), v2_pass, len(selected)))
    return rows


def main() -> None:
    cases = load_cases()
    rows = score(cases)
    failures = [
        case["id"]
        for case in cases
        if not matches_expected(v2_evaluate(case["notes"]), case["expected"])
    ]
    if failures:
        raise SystemExit(f"v2 expectation failures: {', '.join(failures)}")

    print(f"Cases: {len(cases)} synthetic public-safe inputs")
    print("Metric | formatter-only baseline | v2")
    print("---|---:|---:")
    for label, baseline_pass, baseline_total, v2_pass, v2_total in rows:
        print(f"{label} | {baseline_pass}/{baseline_total} | {v2_pass}/{v2_total}")


if __name__ == "__main__":
    main()
