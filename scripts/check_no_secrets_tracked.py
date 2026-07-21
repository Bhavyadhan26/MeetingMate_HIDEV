"""Fail if git history contains tracked secret-like files."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = (
    ".env",
    ".env.local",
    ".env.*.local",
    "*_credentials.json",
    "service-account*.json",
    "*.pem",
    "*.key",
)
ALLOWED_FILENAMES = {".env.example"}


def main() -> int:
    paths = tracked_paths_in_history()
    matches = sorted(path for path in paths if is_secret_path(path))
    if matches:
        print("Secret-like files were tracked in git history:")
        for path in matches:
            print(f"- {path}")
        return 1
    print("No .env or credential-like files are tracked in git history.")
    return 0


def tracked_paths_in_history() -> set[str]:
    repo = Path.cwd().resolve().as_posix()
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "log", "--all", "--name-only", "--pretty=format:"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


def is_secret_path(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return False
    filename = parts[-1]
    if filename in ALLOWED_FILENAMES:
        return False
    if "secrets" in parts:
        return True
    return any(fnmatch.fnmatchcase(filename, pattern) for pattern in SECRET_PATTERNS)


if __name__ == "__main__":
    sys.exit(main())
