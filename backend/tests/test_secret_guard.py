import unittest
import sys
from pathlib import Path

for candidate in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    sys.path.insert(0, str(candidate))
from scripts.check_no_secrets_tracked import is_secret_path


class SecretGuardTests(unittest.TestCase):
    def test_secret_like_paths_are_detected(self) -> None:
        self.assertTrue(is_secret_path(".env"))
        self.assertTrue(is_secret_path("backend/service-account-prod.json"))
        self.assertTrue(is_secret_path("ops/google_credentials.json"))
        self.assertTrue(is_secret_path("config/private.key"))
        self.assertTrue(is_secret_path("infra/secrets/token.txt"))

    def test_allowed_template_is_not_detected(self) -> None:
        self.assertFalse(is_secret_path(".env.example"))
        self.assertFalse(is_secret_path("README.md"))


if __name__ == "__main__":
    unittest.main()
