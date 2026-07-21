import os
import unittest
from unittest.mock import patch

from backend.app.agents.adk_runtime import detect_adk_runtime
from backend.app.memory.vector_store import LocalVectorMemory, get_memory


class IntegrationConfigTests(unittest.TestCase):
    def test_get_memory_defaults_to_local(self) -> None:
        with patch.dict(os.environ, {"MEMORY_BACKEND": "local"}, clear=False):
            self.assertIsInstance(get_memory(), LocalVectorMemory)

    def test_qdrant_backend_reports_missing_dependency_or_connection_clearly(self) -> None:
        with patch.dict(os.environ, {"MEMORY_BACKEND": "qdrant", "QDRANT_URL": "http://localhost:6333"}, clear=False):
            try:
                get_memory()
            except Exception as exc:
                message = str(exc).lower()
                self.assertTrue("qdrant" in message or "connection" in message)
            else:
                self.skipTest("Qdrant is installed and reachable in this environment.")

    def test_adk_detection_is_nonfatal(self) -> None:
        status = detect_adk_runtime()
        self.assertIsInstance(status.available, bool)
        self.assertTrue(status.detail)


if __name__ == "__main__":
    unittest.main()
