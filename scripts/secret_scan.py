"""Pattern-based secret scan for safe, text source files in this project.

All .env-style files and generated/private-data paths are skipped before any
file contents are opened. This is a focused local scan, not a replacement for
a dedicated repository scanner during publication review.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    "data",
    "var",
    "outputs",
    "reports",
    "private",
    "secrets",
    "uploads",
    "artifacts",
    "storage",
    "tmp",
    "temp",
    "dist",
    "build",
    "coverage",
    "node_modules",
}
EXCLUDED_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
    ".pdf",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".png",
    ".jpg",
    ".jpeg",
    ".zip",
}
TEXT_SUFFIXES = {
    ".py",
    ".sql",
    ".toml",
    ".lock",
    ".md",
    ".yaml",
    ".yml",
    ".txt",
    ".json",
}
RULES = [
    ("private_key_block", re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe_secret", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("stripe_webhook_secret", re.compile(r"\bwhsec_[A-Za-z0-9]{16,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "credential_assignment",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|access[_-]?token|private[_-]?key|secret[_-]?key|password)\s*[:=]\s*["'][A-Za-z0-9/+_=.-]{24,}["']"""
        ),
    ),
    (
        "jwt_credential",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
]


def is_env_file(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered == ".env"
        or lowered.startswith(".env.")
        or ".env." in lowered
        or lowered.endswith(".env")
    )


def safe_text_files() -> tuple[list[Path], int, int]:
    files: list[Path] = []
    excluded_env = 0
    excluded_generated = 0

    def walk(directory: Path) -> None:
        nonlocal excluded_env, excluded_generated
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                excluded_generated += 1
                continue
            if entry.is_dir():
                if is_env_file(entry.name):
                    excluded_env += 1
                    continue
                if entry.name.lower() in EXCLUDED_DIRS:
                    excluded_generated += 1
                    continue
                walk(entry)
                continue
            if not entry.is_file():
                continue
            if is_env_file(entry.name):
                excluded_env += 1
                continue
            if entry.suffix.lower() in EXCLUDED_SUFFIXES:
                excluded_generated += 1
                continue
            if entry.suffix.lower() in TEXT_SUFFIXES or entry.name in {
                "Dockerfile",
                ".gitignore",
            }:
                files.append(entry)

    walk(PROJECT_ROOT)
    return files, excluded_env, excluded_generated


def main() -> int:
    files, excluded_env, excluded_generated = safe_text_files()
    findings: list[tuple[str, int, str]] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # A file unreadable as ordinary UTF-8 text is not treated as source.
            continue
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for line_number, line in enumerate(content.splitlines(), start=1):
            for rule_name, pattern in RULES:
                if pattern.search(line):
                    findings.append((relative, line_number, rule_name))

    print("Scan scope: project text source/docs/lockfile only.")
    print(
        "Excluded before reading: names matching .env, .env.*, *.env (including inside directories); "
        ".git, virtualenv, cache, node_modules, build, coverage, data, var, outputs, reports, "
        "private, secrets, uploads, artifacts, storage, tmp, and temp directories; "
        "database, log, PDF, image, key, certificate, archive files, and symlinks."
    )
    print(
        f"Scanned {len(files)} text file(s); excluded {excluded_env} .env-style file(s) "
        f"and {excluded_generated} generated/private path(s)."
    )
    if findings:
        for relative, line_number, rule_name in findings:
            # Report location/rule only; never echo a possible credential value.
            print(f"FINDING {relative}:{line_number} rule={rule_name}")
        print(f"Secret scan: {len(findings)} finding(s).")
        return 1
    print("Secret scan: 0 findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
