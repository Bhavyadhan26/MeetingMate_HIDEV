"""Clone the repo to a temp directory and run the README demo stack there."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    suffix = uuid4().hex[:8]
    project = f"meetingmatefresh{suffix}"
    api_port = 18000 + int(suffix[:2], 16)
    frontend_port = 15173 + int(suffix[2:4], 16)
    qdrant_port = 16333 + int(suffix[4:6], 16)
    qdrant_grpc_port = 16334 + int(suffix[6:8], 16)
    temp_root = Path(tempfile.mkdtemp(prefix="meetingmate-fresh-"))
    clone = temp_root / "repo"
    try:
        run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "clone", "--no-hardlinks", str(ROOT), str(clone)], cwd=ROOT)
        if os.getenv("FRESH_CLONE_INCLUDE_WORKTREE", "").lower() in {"1", "true", "yes"}:
            overlay_worktree(clone)
        rewrite_compose_ports(clone / "docker-compose.yml", api_port, frontend_port, qdrant_port, qdrant_grpc_port)
        (clone / "frontend" / "src" / "config.js").write_text(
            f'window.MEETINGMATE_API_BASE = "http://localhost:{api_port}";\n',
            encoding="utf-8",
        )
        run(["docker", "compose", "-p", project, "up", "-d", "--build"], cwd=clone, timeout=300)
        wait_for_url(f"http://localhost:{qdrant_port}/collections")
        wait_for_url(f"http://localhost:{api_port}/openapi.json")
        wait_for_frontend(frontend_port, api_port)
        demo = run_json(
            [sys.executable, "scripts/demo_walkthrough.py"],
            cwd=clone,
            env={
                "DEMO_API_BASE": f"http://localhost:{api_port}",
                "DEMO_QDRANT_BASE": f"http://localhost:{qdrant_port}",
            },
            timeout=180,
        )
        assert demo["demo_walkthrough"] == "ok", demo
        assert demo["orchestration"] == "adk parallel extraction, sequential drift write", demo
        print(
            json.dumps(
                {
                    "fresh_clone_audit": "ok",
                    "project": project,
                    "api_port": api_port,
                    "frontend_port": frontend_port,
                    "qdrant_port": qdrant_port,
                    "team_id": demo["team_id"],
                    "conflict_id": demo["conflict_id"],
                    "orchestration": demo["orchestration"],
                },
                indent=2,
            )
        )
    finally:
        if clone.exists():
            subprocess.run(["docker", "compose", "-p", project, "down", "-v"], cwd=clone, text=True, capture_output=True, timeout=120)
        shutil.rmtree(temp_root, ignore_errors=True)
    return 0


def rewrite_compose_ports(path: Path, api_port: int, frontend_port: int, qdrant_port: int, qdrant_grpc_port: int) -> None:
    content = path.read_text(encoding="utf-8")
    replacements = {
        '"6333:6333"': f'"{qdrant_port}:6333"',
        '"6334:6334"': f'"{qdrant_grpc_port}:6334"',
        '"8000:8000"': f'"{api_port}:8000"',
        '"5173:80"': f'"{frontend_port}:80"',
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")


def overlay_worktree(clone: Path) -> None:
    tracked = run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files"], cwd=ROOT)
    untracked = run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "--others", "--exclude-standard"], cwd=ROOT)
    for relative in [line for line in (tracked + "\n" + untracked).splitlines() if line.strip()]:
        source = ROOT / relative
        target = clone / relative
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def wait_for_url(url: str, timeout: int = 120) -> str:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - retry all startup failures
            last_error = exc
            time.sleep(2)
    raise TimeoutError(f"{url} did not become ready: {last_error}")


def wait_for_frontend(port: int, api_port: int) -> None:
    index = wait_for_url(f"http://localhost:{port}/index.html")
    assert "./config.js" in index
    config = wait_for_url(f"http://localhost:{port}/config.js")
    assert f"http://localhost:{api_port}" in config
    client = wait_for_url(f"http://localhost:{port}/api/client.js")
    assert "MEETINGMATE_API_BASE" in client


def run(command: list[str], cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=merged_env, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"{command} exited {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result.stdout


def run_json(command: list[str], cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> dict:
    output = run(command, cwd, timeout, env=env)
    return json.loads(output)


if __name__ == "__main__":
    raise SystemExit(main())
