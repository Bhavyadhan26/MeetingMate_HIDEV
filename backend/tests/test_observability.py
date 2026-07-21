import os
import unittest
from unittest.mock import patch

from backend.app.observability.otlp_smoke import has_otlp_exporter, run_otlp_smoke
from backend.app.observability.tracing import _otlp_headers


class ObservabilityTests(unittest.TestCase):
    def test_otlp_headers_accept_json_and_api_key(self) -> None:
        with patch.dict(os.environ, {
            "LYZR_OTLP_HEADERS": '{"x-api-key":"abc"}',
            "LYZR_API_KEY": "secret",
        }, clear=False):
            self.assertEqual(_otlp_headers()["x-api-key"], "abc")
            self.assertEqual(_otlp_headers()["Authorization"], "Bearer secret")

    def test_otlp_headers_accept_key_value_list(self) -> None:
        with patch.dict(os.environ, {"LYZR_OTLP_HEADERS": "x-tenant=demo,x-env=local"}, clear=False):
            headers = _otlp_headers()
            self.assertEqual(headers["x-tenant"], "demo")
            self.assertEqual(headers["x-env"], "local")

    def test_otlp_smoke_exports_span_when_opentelemetry_is_installed(self) -> None:
        if not has_otlp_exporter():
            self.skipTest("OpenTelemetry is not installed in this Python runtime.")
        result = run_otlp_smoke()
        self.assertGreaterEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["path"], "/v1/traces")
        self.assertGreater(result["requests"][0]["content_length"], 0)


if __name__ == "__main__":
    unittest.main()
