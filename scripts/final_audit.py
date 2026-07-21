"""Run the release audit checks for the meeting intelligence project."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILES = {
    "MASTER_BUILD_PROMPT.md",
    "Product-Requirements-Document-PRD-AI-Meeting-Intelligence-Pl.md",
    "final_audit.py",
}
RUNTIME_FILES = {
    "backend/app/memory/local_ledger.json",
    "backend/app/observability/local_traces.jsonl",
}
REQUIRED_PATHS = (
    "README.md",
    ".gitignore",
    ".env.example",
    "docker-compose.yml",
    "docs/ARCHITECTURE.md",
    "docs/AGENTS.md",
    "docs/MEMORY.md",
    "docs/EVAL.md",
    "docs/DEMO_SCRIPT.md",
    "backend/app/main.py",
    "backend/app/api",
    "backend/app/agents/manager.py",
    "backend/app/agents/summarizer.py",
    "backend/app/agents/action_item_extractor.py",
    "backend/app/agents/decision_extractor.py",
    "backend/app/agents/decision_drift_agent.py",
    "backend/app/agents/recall_agent.py",
    "backend/app/memory",
    "backend/app/services",
    "backend/app/models",
    "backend/app/observability",
    "backend/tests",
    "backend/requirements.txt",
    "frontend/src/components",
    "frontend/src/pages",
    "frontend/src/api/client.js",
    "frontend/package.json",
    "scripts/seed_demo_data.py",
    "scripts/run_eval.py",
    "scripts/demo_walkthrough.py",
    "scripts/check_no_secrets_tracked.py",
)
README_TERMS = (
    "Decision Decay",
    "Architecture",
    "Tech Stack",
    "Setup",
    "Demo",
    "Eval",
    "Known Limitations",
    "Project Structure",
    "Google ADK",
    "Qdrant",
    "Lyzr",
)


def main() -> int:
    checks = [
        ("required structure", check_required_structure),
        ("README required content", check_readme_content),
        ("no TODO/FIXME/hardcoded markers", check_no_markers),
        ("no tracked secrets in history", lambda: run([python(), "scripts/check_no_secrets_tracked.py"])),
        ("backend unit tests", lambda: run([python(), "-m", "unittest", "discover", "-s", "backend/tests"])),
        ("python compileall", lambda: run([python(), "-m", "compileall", "backend", "scripts"])),
        ("drift eval", lambda: run([python(), "scripts/run_eval.py"])),
        ("frontend syntax main", lambda: run(["node", "--check", "frontend/src/main.js"])),
        ("frontend syntax api client", lambda: run(["node", "--check", "frontend/src/api/client.js"])),
    ]
    if os.getenv("FINAL_AUDIT_LIVE", "").lower() in {"1", "true", "yes"}:
        checks.extend(
            [
                ("live demo walkthrough", lambda: run([python(), "scripts/demo_walkthrough.py"])),
                ("live Qdrant collections", check_live_qdrant_collections),
            ]
        )

    for name, check in checks:
        print(f"== {name} ==")
        check()
    print("final_audit=ok")
    return 0


def check_required_structure() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    if missing:
        raise AssertionError(f"missing required paths: {missing}")
    print(f"required_paths={len(REQUIRED_PATHS)}")


def check_readme_content() -> None:
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [term for term in README_TERMS if term not in content]
    if missing:
        raise AssertionError(f"README is missing required terms: {missing}")
    print(f"readme_terms={len(README_TERMS)}")


def check_no_markers() -> None:
    markers = ("todo", "fixme", "hardcoded")
    matches: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in PROMPT_FILES:
            continue
        if path.relative_to(ROOT).as_posix() in RUNTIME_FILES:
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            if any(marker in lower for marker in markers):
                matches.append(f"{path.relative_to(ROOT)}:{line_number}:{line.strip()}")
    if matches:
        raise AssertionError("marker scan failed:\n" + "\n".join(matches))
    print("marker_scan=ok")


def check_live_qdrant_collections() -> None:
    with urllib.request.urlopen("http://localhost:6333/collections", timeout=10) as response:
        body = response.read().decode("utf-8")
    missing = [name for name in ("decisions", "action_items", "meeting_chunks") if name not in body]
    if missing:
        raise AssertionError(f"missing live Qdrant collections: {missing}")
    print("qdrant_collections=ok")


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=merged_env)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if result.returncode != 0:
        raise RuntimeError(f"{command} exited {result.returncode}")


def python() -> str:
    return sys.executable


if __name__ == "__main__":
    raise SystemExit(main())
