from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.security import decrypt_json, encrypt_json


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetadataStore:
    def __init__(self, database_url: str | None = None, sqlite_path: str | None = None) -> None:
        self.database_url = database_url if database_url is not None else ("" if sqlite_path is not None else os.getenv("DATABASE_URL", ""))
        self.sqlite_path = sqlite_path or os.getenv("SQLITE_METADATA_PATH", "backend/app/persistence/meetingmate.sqlite3")
        self.backend = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._initialize()

    def _connect(self) -> Any:
        if self.backend == "postgres":
            import psycopg

            return psycopg.connect(self.database_url)
        path = Path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                title TEXT NOT NULL,
                attendees_json TEXT NOT NULL,
                agenda_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS redaction_maps (
                meeting_id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                redaction_map_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transcript_jobs (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                audio_path TEXT,
                content_type TEXT,
                result_json TEXT,
                error_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS team_memberships (
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (team_id, user_id)
            )
            """,
        ]
        connection = self._connect()
        try:
            for statement in statements:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()

    def save_processing_result(self, result: Any) -> None:
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        meeting = payload["meeting"]
        transcript = payload["transcript"]
        self.save_meeting(meeting)
        self.save_redaction_map(transcript["meeting_id"], transcript["team_id"], transcript.get("redaction_map", {}))

    def save_meeting(self, meeting: Dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO meetings (id, team_id, title, attendees_json, agenda_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                team_id=excluded.team_id,
                title=excluded.title,
                attendees_json=excluded.attendees_json,
                agenda_json=excluded.agenda_json,
                created_at=excluded.created_at
            """,
            (
                meeting["id"],
                meeting["team_id"],
                meeting["title"],
                json.dumps(meeting.get("attendees", []), default=str),
                json.dumps(meeting.get("agenda", []), default=str),
                str(meeting.get("created_at") or utcnow_iso()),
            ),
        )

    def save_redaction_map(self, meeting_id: str, team_id: str, redaction_map: Dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO redaction_maps (meeting_id, team_id, redaction_map_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                team_id=excluded.team_id,
                redaction_map_json=excluded.redaction_map_json
            """,
            (meeting_id, team_id, encrypt_json(redaction_map), utcnow_iso()),
        )

    def get_redaction_map(self, meeting_id: str) -> Dict[str, Any]:
        row = self._fetch_one("SELECT redaction_map_json FROM redaction_maps WHERE meeting_id = ?", (meeting_id,))
        if not row:
            return {}
        value = row["redaction_map_json"] if not isinstance(row, dict) else row["redaction_map_json"]
        return decrypt_json(value)

    def sync_user_context(self, subject: str, email: str, roles: set[str], teams: set[str]) -> None:
        primary_role = sorted(roles)[0] if roles else "member"
        self._execute(
            """
            INSERT INTO users (id, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET email=excluded.email, role=excluded.role
            """,
            (subject, email or f"{subject}@auth0.local", "auth0", primary_role, utcnow_iso()),
        )
        for team_id in teams:
            if team_id == "*":
                continue
            self._execute(
                """
                INSERT INTO teams (id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name
                """,
                (team_id, team_id, utcnow_iso()),
            )
            self._execute(
                """
                INSERT INTO team_memberships (team_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id, user_id) DO UPDATE SET role=excluded.role
                """,
                (team_id, subject, primary_role, utcnow_iso()),
            )

    def create_job(self, job: Dict[str, Any], payload: Dict[str, Any], kind: str, audio_path: str | None = None, content_type: str | None = None) -> None:
        self._execute(
            """
            INSERT INTO transcript_jobs (job_id, kind, status, payload_json, audio_path, content_type, result_json, error_json, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["job_id"],
                kind,
                job["status"],
                json.dumps(payload, default=str),
                audio_path,
                content_type,
                None,
                None,
                job["created_at"],
                job["updated_at"],
                job.get("expires_at"),
            ),
        )

    def update_job(self, job_id: str, **fields: Any) -> None:
        allowed = {"status", "result", "error", "updated_at", "expires_at"}
        columns: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            column = {"result": "result_json", "error": "error_json"}.get(key, key)
            columns.append(f"{column} = ?")
            if key in {"result", "error"}:
                values.append(None if value is None else json.dumps(value, default=str))
            else:
                values.append(value)
        if not columns:
            return
        values.append(job_id)
        self._execute(f"UPDATE transcript_jobs SET {', '.join(columns)} WHERE job_id = ?", tuple(values))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetch_one("SELECT * FROM transcript_jobs WHERE job_id = ?", (job_id,))
        return self._job_from_row(row) if row else None

    def next_queued_job(self) -> Optional[Dict[str, Any]]:
        row = self._fetch_one(
            "SELECT * FROM transcript_jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
            ("queued",),
        )
        return self._job_from_row(row) if row else None

    def mark_stale_processing_jobs_queued(self) -> None:
        self._execute("UPDATE transcript_jobs SET status = ?, updated_at = ? WHERE status = ?", ("queued", utcnow_iso(), "processing"))

    def purge_expired_jobs(self) -> None:
        self._execute(
            "DELETE FROM transcript_jobs WHERE status IN (?, ?) AND expires_at IS NOT NULL AND expires_at <= ?",
            ("completed", "failed", utcnow_iso()),
        )

    def _job_from_row(self, row: Any) -> Dict[str, Any]:
        get = row.get if isinstance(row, dict) else lambda key: row[key]
        result_raw = get("result_json")
        error_raw = get("error_json")
        payload_raw = get("payload_json")
        return {
            "job_id": get("job_id"),
            "kind": get("kind"),
            "status": get("status"),
            "payload": json.loads(payload_raw or "{}"),
            "audio_path": get("audio_path"),
            "content_type": get("content_type"),
            "created_at": get("created_at"),
            "updated_at": get("updated_at"),
            "expires_at": get("expires_at"),
            "result": json.loads(result_raw) if result_raw else None,
            "error": json.loads(error_raw) if error_raw else None,
        }

    def _execute(self, statement: str, params: tuple[Any, ...] = ()) -> None:
        sql = self._sql(statement)
        connection = self._connect()
        try:
            connection.execute(sql, params)
            connection.commit()
        finally:
            connection.close()

    def _fetch_one(self, statement: str, params: tuple[Any, ...] = ()) -> Optional[Any]:
        sql = self._sql(statement)
        connection = self._connect()
        try:
            cursor = connection.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None
            if self.backend == "postgres":
                columns = [column.name for column in cursor.description]
                return dict(zip(columns, row))
            return row
        finally:
            connection.close()

    def _sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self.backend == "postgres" else statement


_store: Optional[MetadataStore] = None


def get_metadata_store() -> MetadataStore:
    global _store
    if _store is None:
        _store = MetadataStore()
    return _store
