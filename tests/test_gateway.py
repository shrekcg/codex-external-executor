from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen


SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "external-model-executor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from external_executor_lib.config import AppConfig, RouteConfig  # noqa: E402
from external_executor_lib.gateway import LoopbackHTTPServer, make_handler  # noqa: E402


class FakeUpstream(BaseHTTPRequestHandler):
    requests: list[tuple[str, dict]] = []

    def log_message(self, format_string: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        self.__class__.requests.append((self.path, body))
        if self.path == "/chat/completions":
            payload = {
                "model": body["model"],
                "choices": [{"message": {"role": "assistant", "content": "adapter-ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
        else:
            payload = {
                "id": "resp_fake",
                "object": "response",
                "status": "completed",
                "model": body["model"],
                "output": [],
            }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeUpstream.requests = []
        self.upstream = LoopbackHTTPServer(("127.0.0.1", 0), FakeUpstream)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        os.environ["TEST_EXTERNAL_KEY"] = "test-only-key"

    def tearDown(self) -> None:
        self.upstream.shutdown()
        self.upstream.server_close()
        os.environ.pop("TEST_EXTERNAL_KEY", None)

    def _route(self, protocol: str) -> RouteConfig:
        return RouteConfig(
            name="test-route",
            provider="test",
            model="real-model",
            protocol=protocol,
            base_url=f"http://127.0.0.1:{self.upstream.server_port}",
            api_key_env="TEST_EXTERNAL_KEY",
        )

    def _gateway(self, route: RouteConfig) -> LoopbackHTTPServer:
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig(
                path=Path(directory) / "config.json",
                host="127.0.0.1",
                port=0,
                state_dir=Path(directory),
                routes={route.name: route},
            )
            server = LoopbackHTTPServer(("127.0.0.1", 0), make_handler(config))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_chat_route_returns_responses_shape(self) -> None:
        gateway = self._gateway(self._route("openai_chat"))
        try:
            body = {"model": "test-route", "input": "hello", "stream": False}
            request = Request(
                f"http://127.0.0.1:{gateway.server_port}/v1/responses",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                result = json.loads(response.read())
            self.assertEqual(result["object"], "response")
            self.assertEqual(result["output"][0]["content"][0]["text"], "adapter-ok")
            self.assertEqual(FakeUpstream.requests[0][0], "/chat/completions")
            self.assertEqual(FakeUpstream.requests[0][1]["model"], "real-model")
        finally:
            gateway.shutdown()
            gateway.server_close()

    def test_responses_route_replaces_route_name(self) -> None:
        gateway = self._gateway(self._route("responses"))
        try:
            body = {"model": "test-route", "input": "hello", "stream": False}
            request = Request(
                f"http://127.0.0.1:{gateway.server_port}/v1/responses",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                result = json.loads(response.read())
            self.assertEqual(result["model"], "real-model")
            self.assertEqual(FakeUpstream.requests[0][0], "/responses")
            self.assertEqual(FakeUpstream.requests[0][1]["model"], "real-model")
        finally:
            gateway.shutdown()
            gateway.server_close()

    def test_translated_stream_emits_responses_sse(self) -> None:
        gateway = self._gateway(self._route("openai_chat"))
        try:
            body = {"model": "test-route", "input": "hello", "stream": True}
            request = Request(
                f"http://127.0.0.1:{gateway.server_port}/v1/responses",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                stream = response.read().decode()
            self.assertIn("event: response.output_text.delta", stream)
            self.assertIn("adapter-ok", stream)
            self.assertIn("event: response.completed", stream)
        finally:
            gateway.shutdown()
            gateway.server_close()


if __name__ == "__main__":
    unittest.main()
