"""Loopback Responses API gateway used by Codex model providers."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socketserver
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig, ConfigError, RouteConfig
from .protocol import (
    ProtocolError,
    anthropic_to_response,
    chat_to_response,
    response_sse_events,
    responses_to_anthropic,
    responses_to_chat,
)


LOG = logging.getLogger("external-executor-gateway")


class LoopbackHTTPServer(ThreadingHTTPServer):
    """HTTP server that avoids reverse-DNS lookup during loopback binding."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)


class UpstreamError(RuntimeError):
    def __init__(self, status: int, message: str, body: bytes = b"") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _endpoint(route: RouteConfig) -> str:
    suffix = "/responses" if route.protocol == "responses" else "/chat/completions"
    if route.protocol == "anthropic_messages":
        suffix = "/messages"
    return route.base_url.rstrip("/") + suffix


def _request_json(route: RouteConfig, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    request = Request(
        _endpoint(route),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=route.request_headers(),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        body = exc.read()
        raise UpstreamError(exc.code, f"Upstream returned HTTP {exc.code}", body) from exc
    except URLError as exc:
        raise UpstreamError(502, f"Unable to reach upstream: {exc.reason}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UpstreamError(502, "Upstream returned invalid JSON", raw[:2048]) from exc
    if not isinstance(result, dict):
        raise UpstreamError(502, "Upstream returned a non-object JSON response")
    return result


def _clean_responses_request(route: RouteConfig, body: dict[str, Any]) -> dict[str, Any]:
    clean = {key: value for key, value in body.items() if key not in route.drop_request_fields}
    clean["model"] = route.model
    if "no_reasoning_encrypted_content" in route.limitations:
        include = clean.get("include")
        if isinstance(include, list):
            filtered = [value for value in include if value != "reasoning.encrypted_content"]
            if filtered:
                clean["include"] = filtered
            else:
                clean.pop("include", None)
    return clean


def execute_translated(route: RouteConfig, body: dict[str, Any]) -> dict[str, Any]:
    if route.protocol == "openai_chat":
        request_body, custom_tools = responses_to_chat(body, route.model)
        return chat_to_response(_request_json(route, request_body), custom_tools)
    if route.protocol == "anthropic_messages":
        request_body, custom_tools = responses_to_anthropic(body, route.model)
        return anthropic_to_response(_request_json(route, request_body), custom_tools)
    raise ProtocolError(f"Route {route.name} is not a translated protocol")


def probe_route(route: RouteConfig, include_tools: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": route.name,
        "input": "Reply with exactly: EXTERNAL_EXECUTOR_OK",
        "max_output_tokens": 32,
        "stream": False,
    }
    if include_tools:
        body["input"] = "Call the echo tool with the value ok."
        body["tools"] = [
            {
                "type": "function",
                "name": "echo",
                "description": "Echo a value",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            }
        ]
    if route.protocol == "responses":
        return _request_json(route, _clean_responses_request(route, body))
    return execute_translated(route, body)


def make_handler(config: AppConfig) -> type[BaseHTTPRequestHandler]:
    class GatewayHandler(BaseHTTPRequestHandler):
        server_version = "CodexExternalExecutor/1.0"

        def log_message(self, format_string: str, *args: object) -> None:
            LOG.info("%s - %s", self.client_address[0], format_string % args)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path in {"/health", "/v1/health"}:
                self._json(
                    200,
                    {
                        "status": "ok",
                        "version": 1,
                        "routes": {
                            name: {"provider": route.provider, "protocol": route.protocol}
                            for name, route in config.routes.items()
                        },
                    },
                )
                return
            if self.path == "/v1/models":
                self._json(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {"id": name, "object": "model", "owned_by": route.provider}
                            for name, route in config.routes.items()
                        ],
                    },
                )
                return
            self._json(404, {"error": {"message": "Not found", "type": "not_found"}})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path.rstrip("/") not in {"/responses", "/v1/responses"}:
                self._json(404, {"error": {"message": "Not found", "type": "not_found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16 * 1024 * 1024:
                    raise ProtocolError("Request body must be between 1 byte and 16 MiB")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ProtocolError("Request body must be a JSON object")
                route_name = body.get("model")
                route = config.routes.get(route_name)
                if route is None:
                    raise ProtocolError(f"Unknown route model: {route_name!r}")
                LOG.info("route=%s protocol=%s stream=%s", route.name, route.protocol, bool(body.get("stream")))
                if route.protocol == "responses":
                    self._proxy_responses(route, body)
                else:
                    self._translated_response(route, body)
            except (json.JSONDecodeError, ProtocolError, ConfigError) as exc:
                self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
            except UpstreamError as exc:
                self._upstream_error(exc)
            except BrokenPipeError:
                LOG.info("Client disconnected")
            except Exception as exc:  # pragma: no cover - final safety boundary
                LOG.exception("Unhandled gateway error")
                self._json(500, {"error": {"message": str(exc), "type": "gateway_error"}})

        def _proxy_responses(self, route: RouteConfig, body: dict[str, Any]) -> None:
            clean = _clean_responses_request(route, body)
            request = Request(
                _endpoint(route),
                data=json.dumps(clean, ensure_ascii=False).encode("utf-8"),
                headers=route.request_headers(),
                method="POST",
            )
            try:
                upstream = urlopen(request, timeout=300)
            except HTTPError as exc:
                raise UpstreamError(exc.code, f"Upstream returned HTTP {exc.code}", exc.read()) from exc
            except URLError as exc:
                raise UpstreamError(502, f"Unable to reach upstream: {exc.reason}") from exc
            with upstream:
                self.send_response(upstream.status)
                content_type = upstream.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                while True:
                    chunk = upstream.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()

        def _translated_response(self, route: RouteConfig, body: dict[str, Any]) -> None:
            response = execute_translated(route, body)
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                for event_name, payload in response_sse_events(response):
                    frame = f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()
            else:
                self._json(200, response)

        def _upstream_error(self, exc: UpstreamError) -> None:
            if exc.body:
                try:
                    payload = json.loads(exc.body)
                    if isinstance(payload, dict):
                        self._json(exc.status, payload)
                        return
                except json.JSONDecodeError:
                    pass
            self._json(exc.status, {"error": {"message": str(exc), "type": "upstream_error"}})

    return GatewayHandler


def serve(config: AppConfig) -> None:
    server = LoopbackHTTPServer((config.host, config.port), make_handler(config))
    LOG.info("Listening on http://%s:%s with %s route(s)", config.host, config.port, len(config.routes))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
