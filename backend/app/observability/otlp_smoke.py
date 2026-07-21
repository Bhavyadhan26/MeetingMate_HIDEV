from __future__ import annotations

import json
import importlib.util
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, List


class _OtlpCaptureHandler(BaseHTTPRequestHandler):
    requests: List[dict[str, Any]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.requests.append({
            "path": self.path,
            "content_type": self.headers.get("content-type", ""),
            "content_length": len(body),
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: Any) -> None:
        return


def has_otlp_exporter() -> bool:
    try:
        return (
            importlib.util.find_spec("opentelemetry") is not None
            and importlib.util.find_spec("opentelemetry.sdk") is not None
            and importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http.trace_exporter") is not None
        )
    except ModuleNotFoundError:
        return False


def run_otlp_smoke() -> dict[str, Any]:
    if not has_otlp_exporter():
        raise RuntimeError("OpenTelemetry SDK/exporter is not installed in this Python runtime.")

    server = HTTPServer(("127.0.0.1", 0), _OtlpCaptureHandler)
    _OtlpCaptureHandler.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
    old_endpoint = os.environ.get("LYZR_OTLP_ENDPOINT")
    old_headers = os.environ.get("LYZR_OTLP_HEADERS")
    os.environ["LYZR_OTLP_ENDPOINT"] = endpoint
    os.environ["LYZR_OTLP_HEADERS"] = json.dumps({"x-lyzr-smoke": "true"})
    try:
        from backend.app.observability.tracing import flush_traces, shutdown_traces, trace_event

        trace_id = trace_event("otlp_smoke", "export", {"component": "otlp_smoke", "smoke": True})
        flush_traces()
        deadline = time.time() + 5
        while time.time() < deadline and not _OtlpCaptureHandler.requests:
            time.sleep(0.05)
        if not _OtlpCaptureHandler.requests:
            raise RuntimeError("No OTLP request was received by the local smoke receiver.")
        return {
            "trace_id": trace_id,
            "endpoint": endpoint,
            "requests": _OtlpCaptureHandler.requests,
        }
    finally:
        try:
            shutdown_traces()
        except UnboundLocalError:
            pass
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        if old_endpoint is None:
            os.environ.pop("LYZR_OTLP_ENDPOINT", None)
        else:
            os.environ["LYZR_OTLP_ENDPOINT"] = old_endpoint
        if old_headers is None:
            os.environ.pop("LYZR_OTLP_HEADERS", None)
        else:
            os.environ["LYZR_OTLP_HEADERS"] = old_headers


if __name__ == "__main__":
    print(json.dumps(run_otlp_smoke(), indent=2))
