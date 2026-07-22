import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.persistence.database import MetadataStore
from backend.app.security import UserContext, auth_required, decrypt_json, encrypt_json, require_role, require_team_access


class SecurityTests(unittest.TestCase):
    def test_team_access_rejects_non_member(self) -> None:
        user = UserContext(subject="auth0|u1", email="u1@example.com", roles={"member"}, teams={"alpha"}, claims={})
        with self.assertRaises(HTTPException) as raised:
            require_team_access(user, "beta")
        self.assertEqual(raised.exception.status_code, 403)

    def test_auth_auto_enables_when_auth0_is_configured(self) -> None:
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "example.auth0.com", "AUTH0_AUDIENCE": "meetingmate"}, clear=True):
            self.assertTrue(auth_required())
        with patch.dict(os.environ, {"AUTH_REQUIRED": "0", "AUTH0_DOMAIN": "example.auth0.com", "AUTH0_AUDIENCE": "meetingmate"}, clear=True):
            self.assertFalse(auth_required())

    def test_admin_can_access_any_team_and_admin_actions(self) -> None:
        user = UserContext(subject="auth0|admin", email="admin@example.com", roles={"admin"}, teams=set(), claims={})
        require_team_access(user, "beta")
        require_role(user, {"platform_admin"})

    def test_redaction_maps_are_encrypted_at_rest(self) -> None:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        os.unlink(tmp.name)
        try:
            with patch.dict(os.environ, {"REDACTION_MAP_ENCRYPTION_KEY": "unit-test-key"}, clear=False):
                store = MetadataStore(sqlite_path=tmp.name)
                store.save_redaction_map("meeting-1", "team-1", {"Asha Rao": "[PERSON_1]"})
                row = store._fetch_one("SELECT redaction_map_json FROM redaction_maps WHERE meeting_id = ?", ("meeting-1",))
                encrypted = row["redaction_map_json"]
                self.assertTrue(encrypted.startswith("aesgcm256:"))
                self.assertNotIn("Asha Rao", encrypted)
                self.assertEqual(store.get_redaction_map("meeting-1"), {"Asha Rao": "[PERSON_1]"})
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def test_encrypt_json_round_trip(self) -> None:
        with patch.dict(os.environ, {"REDACTION_MAP_ENCRYPTION_KEY": "unit-test-key"}, clear=False):
            encrypted = encrypt_json({"Marco": "[PERSON_1]"})
            self.assertNotIn("Marco", encrypted)
            self.assertEqual(decrypt_json(encrypted), {"Marco": "[PERSON_1]"})

    def test_auth_required_blocks_missing_bearer_token_but_config_is_public(self) -> None:
        from backend.app.main import app

        with patch.dict(os.environ, {"AUTH_REQUIRED": "1", "AUTH0_DOMAIN": "example.auth0.com", "AUTH0_AUDIENCE": "meetingmate"}, clear=False):
            client = TestClient(app)
            blocked = client.get("/v1/memory/search?query=qdrant&team_id=alpha")
            config = client.get("/v1/auth/config")
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["detail"]["code"], "auth_required")
        self.assertEqual(config.status_code, 200)
        self.assertTrue(config.json()["required"])


if __name__ == "__main__":
    unittest.main()
