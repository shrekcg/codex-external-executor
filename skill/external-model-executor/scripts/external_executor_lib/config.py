"""Configuration loading, preset resolution, and secret retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


ROUTE_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
SUPPORTED_PROTOCOLS = {"responses", "openai_chat", "anthropic_messages"}


class ConfigError(ValueError):
    """Raised when local configuration is invalid."""


def default_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "codex-external-executor" / "config.json"


def default_state_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "codex-external-executor"


def _preset_path() -> Path:
    return Path(__file__).resolve().parent.parent / "provider_presets.json"


def load_presets() -> dict[str, dict[str, Any]]:
    with _preset_path().open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ConfigError("provider_presets.json must contain an object")
    return data


@dataclass(frozen=True)
class RouteConfig:
    name: str
    provider: str
    model: str
    protocol: str
    base_url: str
    api_key_env: str | None
    api_key_command: tuple[str, ...] = ()
    auth: str = "bearer"
    brief_mode: str = "auto"
    headers: dict[str, str] = field(default_factory=dict)
    header_env: dict[str, str] = field(default_factory=dict)
    drop_request_fields: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def resolve_api_key(self) -> str:
        if self.api_key_command:
            try:
                result = subprocess.run(
                    list(self.api_key_command),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ConfigError(f"API key command failed for route {self.name}: {exc}") from exc
            secret = result.stdout.strip()
        elif self.api_key_env:
            secret = os.environ.get(self.api_key_env, "").strip()
        else:
            secret = ""
        if not secret:
            source = "command" if self.api_key_command else self.api_key_env or "configuration"
            raise ConfigError(f"API key is unavailable for route {self.name} via {source}")
        return secret

    def request_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.headers}
        if self.auth == "anthropic":
            secret = self.resolve_api_key()
            headers["x-api-key"] = secret
            headers.setdefault("anthropic-version", "2023-06-01")
        elif self.auth == "bearer":
            secret = self.resolve_api_key()
            headers["Authorization"] = f"Bearer {secret}"
        elif self.auth != "none":
            raise ConfigError(f"Unsupported auth mode for route {self.name}: {self.auth}")
        for header, env_name in self.header_env.items():
            value = os.environ.get(env_name, "").strip()
            if not value:
                raise ConfigError(f"Header environment variable {env_name} is unavailable")
            headers[header] = value
        return headers


@dataclass(frozen=True)
class AppConfig:
    path: Path
    host: str
    port: int
    state_dir: Path
    routes: dict[str, RouteConfig]


def _string_map(value: Any, label: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ConfigError(f"{label} must be an object of string values")
    return dict(value)


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path).expanduser() if path else default_config_path()
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc
    if raw.get("version") != 1:
        raise ConfigError("Configuration version must be 1")
    server = raw.get("server", {})
    host = server.get("host", "127.0.0.1")
    port = server.get("port", 8787)
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ConfigError("The gateway must bind to a loopback host")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ConfigError("server.port must be an integer between 1 and 65535")
    state_dir = Path(server.get("state_dir", str(default_state_dir()))).expanduser()
    presets = load_presets()
    route_entries = raw.get("routes")
    if not isinstance(route_entries, dict) or not route_entries:
        raise ConfigError("At least one route is required")
    routes: dict[str, RouteConfig] = {}
    for name, entry in route_entries.items():
        if not isinstance(name, str) or not ROUTE_RE.fullmatch(name):
            raise ConfigError(f"Invalid route name: {name!r}")
        if not isinstance(entry, dict):
            raise ConfigError(f"Route {name} must be an object")
        provider = entry.get("provider")
        if provider not in presets:
            raise ConfigError(f"Unknown provider preset for route {name}: {provider!r}")
        merged = {**presets[provider], **entry}
        model = merged.get("model")
        base_url = str(merged.get("base_url", "")).rstrip("/")
        protocol = merged.get("protocol")
        if not isinstance(model, str) or not model.strip():
            raise ConfigError(f"Route {name} requires a model")
        if not base_url.startswith(("https://", "http://")):
            raise ConfigError(f"Route {name} requires an HTTP(S) base_url")
        if protocol not in SUPPORTED_PROTOCOLS:
            raise ConfigError(f"Unsupported protocol for route {name}: {protocol!r}")
        command = merged.get("api_key_command", [])
        if command and (not isinstance(command, list) or not all(isinstance(part, str) and part for part in command)):
            raise ConfigError(f"Route {name} api_key_command must be a non-empty string array")
        brief_mode = merged.get("brief_mode", "auto")
        if brief_mode not in {"auto", "always", "off"}:
            raise ConfigError(f"Route {name} brief_mode must be auto, always, or off")
        routes[name] = RouteConfig(
            name=name,
            provider=provider,
            model=model.strip(),
            protocol=protocol,
            base_url=base_url,
            api_key_env=merged.get("api_key_env"),
            api_key_command=tuple(command),
            auth=merged.get("auth", "bearer"),
            brief_mode=brief_mode,
            headers=_string_map(merged.get("headers"), f"Route {name} headers"),
            header_env=_string_map(merged.get("header_env"), f"Route {name} header_env"),
            drop_request_fields=tuple(merged.get("drop_request_fields", [])),
            capabilities=tuple(merged.get("capabilities", [])),
            limitations=tuple(merged.get("limitations", [])),
        )
    return AppConfig(path=config_path, host=host, port=port, state_dir=state_dir, routes=routes)


def save_route(
    path: str | Path | None,
    *,
    name: str,
    provider: str,
    model: str,
    base_url: str | None,
    api_key_env: str | None,
    api_key_command: list[str] | None,
    brief_mode: str,
    auth: str | None = None,
    header_env: dict[str, str] | None = None,
    drop_request_fields: list[str] | None = None,
) -> Path:
    if not ROUTE_RE.fullmatch(name):
        raise ConfigError("Route names must match [a-z][a-z0-9-]{0,47}")
    presets = load_presets()
    if provider not in presets:
        raise ConfigError(f"Unknown provider preset: {provider}")
    if not isinstance(model, str) or not model.strip():
        raise ConfigError("model must be a non-empty string")
    if brief_mode not in {"auto", "always", "off"}:
        raise ConfigError("brief_mode must be auto, always, or off")
    if not base_url and not presets[provider].get("base_url"):
        raise ConfigError(f"Provider preset {provider} requires --base-url")
    config_path = Path(path).expanduser() if path else default_config_path()
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    else:
        raw = {
            "version": 1,
            "server": {"host": "127.0.0.1", "port": 8787},
            "routes": {},
        }
    entry: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "brief_mode": brief_mode,
    }
    if base_url:
        entry["base_url"] = base_url.rstrip("/")
    if auth:
        if auth not in {"bearer", "anthropic", "none"}:
            raise ConfigError("auth must be bearer, anthropic, or none")
        entry["auth"] = auth
    if header_env:
        entry["header_env"] = header_env
    if drop_request_fields:
        forbidden = {"model", "input", "tools"}.intersection(drop_request_fields)
        if forbidden:
            raise ConfigError(f"Cannot drop required execution fields: {', '.join(sorted(forbidden))}")
        entry["drop_request_fields"] = sorted(set(drop_request_fields))
    if api_key_command:
        entry["api_key_command"] = api_key_command
        entry["api_key_env"] = None
    elif api_key_env:
        entry["api_key_env"] = api_key_env
    raw.setdefault("routes", {})[name] = entry
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        load_config(temporary)
        if config_path.exists():
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
        temporary.replace(config_path)
    finally:
        temporary.unlink(missing_ok=True)
    return config_path
