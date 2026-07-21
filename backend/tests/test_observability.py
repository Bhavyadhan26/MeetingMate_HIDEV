import io
import json
import os
import urllib.error
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from backend.app.observability.lyzr_live_trace_check import (
    main as lyzr_live_trace_check_main,
    verify_otlp_endpoint_accepts_traces,
)
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

    def test_live_lyzr_trace_check_reports_missing_endpoint_as_json(self) -> None:
        with patch.dict(os.environ, {
            "LYZR_OTLP_ENDPOINT": "",
            "LYZR_API_KEY": "",
            "LYZR_OTLP_HEADERS": "",
        }, clear=False):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = lyzr_live_trace_check_main()
        self.assertEqual(exit_code, 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["lyzr_live_trace_check"], "not_submitted")
        self.assertIn("LYZR_OTLP_ENDPOINT", payload["error"])

    def test_live_lyzr_trace_check_rejects_non_otlp_endpoint(self) -> None:
        if not has_otlp_exporter():
            self.skipTest("OpenTelemetry is not installed in this Python runtime.")
        error = urllib.error.HTTPError(
            url="https://example.test/v1/traces",
            code=405,
            msg="Method Not Allowed",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"Method Not Allowed"}'),
        )
        with patch.dict(os.environ, {"LYZR_OTLP_ENDPOINT": "https://example.test/v1/traces"}, clear=False):
            with patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "status=405"):
                    verify_otlp_endpoint_accepts_traces()


if __name__ == "__main__":
    unittest.main()
