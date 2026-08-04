"""Command-line interface for setup, validation, installation, and gateway control."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from . import __version__
from .codex_install import agent_name, install, render, uninstall
from .config import ConfigError, default_config_path, load_config, load_presets, save_route
from .gateway import ProtocolError, UpstreamError, probe_route, serve


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="external-executor",
        description="Route selected Codex sub-agent tasks to external model APIs.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    providers = sub.add_parser("providers", help="List built-in provider presets")
    providers.add_argument("--json", action="store_true")

    configure = sub.add_parser("configure", help="Create or update one external route")
    configure.add_argument("--config", type=Path, default=default_config_path())
    configure.add_argument("--route", required=True)
    configure.add_argument("--provider", required=True)
    configure.add_argument("--model", required=True)
    configure.add_argument("--base-url")
    configure.add_argument("--api-key-env")
    configure.add_argument("--api-key-command", nargs="+")
    configure.add_argument(
        "--api-key-command-json",
        help='Credential command as a JSON string array, for example ["security","...","-w"]',
    )
    configure.add_argument("--auth", choices=["bearer", "anthropic", "none"])
    configure.add_argument(
        "--header-env",
        action="append",
        default=[],
        metavar="HEADER=ENV",
        help="Resolve a custom upstream header from an environment variable",
    )
    configure.add_argument(
        "--drop-request-field",
        action="append",
        default=[],
        help="Remove an optional Responses request field before a native pass-through call",
    )
    configure.add_argument("--brief-mode", choices=["auto", "always", "off"], default="auto")

    routes = sub.add_parser("routes", help="List configured routes")
    routes.add_argument("--config", type=Path, default=default_config_path())
    routes.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate", help="Validate configuration and optionally call upstream")
    validate.add_argument("--config", type=Path, default=default_config_path())
    validate.add_argument("--route")
    validate.add_argument("--live", action="store_true")
    validate.add_argument("--tools", action="store_true", help="Include a function-calling probe")

    gateway = sub.add_parser("gateway", help="Control the loopback compatibility gateway")
    gateway_sub = gateway.add_subparsers(dest="gateway_command", required=True)
    for name in ("serve", "start", "status", "stop"):
        item = gateway_sub.add_parser(name)
        item.add_argument("--config", type=Path, default=default_config_path())

    codex = sub.add_parser("codex", help="Preview or install Codex provider and sub-agent files")
    codex_sub = codex.add_subparsers(dest="codex_command", required=True)
    preview = codex_sub.add_parser("preview")
    preview.add_argument("--config", type=Path, default=default_config_path())
    preview.add_argument("--route", required=True)
    apply_parser = codex_sub.add_parser("install")
    apply_parser.add_argument("--config", type=Path, default=default_config_path())
    apply_parser.add_argument("--route", required=True)
    apply_parser.add_argument("--apply", action="store_true", help="Required to write into CODEX_HOME")
    uninstall_parser = codex_sub.add_parser("uninstall")
    uninstall_parser.add_argument("--config", type=Path, default=default_config_path())
    uninstall_parser.add_argument("--route", required=True)
    uninstall_parser.add_argument("--apply", action="store_true", help="Required to remove the managed route and Agent")

    brief = sub.add_parser("brief", help="Validate an external task brief")
    brief_sub = brief.add_subparsers(dest="brief_command", required=True)
    brief_validate = brief_sub.add_parser("validate")
    brief_validate.add_argument("path", type=Path)
    brief_validate.add_argument("--task-name", required=True)
    return parser


def _health_url(config: Any) -> str:
    return f"http://{config.host}:{config.port}/health"


def _health(config: Any, timeout: float = 0.5) -> dict[str, Any] | None:
    try:
        with urlopen(_health_url(config), timeout=timeout) as response:
            data = json.loads(response.read())
        return data if isinstance(data, dict) else None
    except (OSError, URLError, json.JSONDecodeError):
        return None


def _gateway_paths(config: Any) -> tuple[Path, Path]:
    return config.state_dir / "gateway.pid", config.state_dir / "gateway.log"


def _gateway_start(config: Any) -> int:
    if _health(config):
        print(f"Gateway already running at {_health_url(config)}")
        return 0
    config.state_dir.mkdir(parents=True, exist_ok=True)
    pid_file, log_file = _gateway_paths(config)
    entry = Path(__file__).resolve().parent.parent / "external_executor.py"
    command = [sys.executable, str(entry), "gateway", "serve", "--config", str(config.path)]
    with log_file.open("ab") as log_handle:
        kwargs: dict[str, Any] = {"stdout": log_handle, "stderr": log_handle, "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    for _ in range(30):
        if _health(config):
            print(f"Gateway started at {_health_url(config)} (pid {process.pid})")
            return 0
        if process.poll() is not None:
            break
        time.sleep(0.1)
    print(f"Gateway failed to start; inspect {log_file}", file=sys.stderr)
    return 1


def _gateway_stop(config: Any) -> int:
    pid_file, _ = _gateway_paths(config)
    if not pid_file.exists():
        print("Gateway PID file not found")
        return 1 if _health(config) else 0
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if pid <= 1:
            raise ValueError
    except ValueError:
        raise ConfigError(f"Invalid gateway PID file: {pid_file}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(20):
        if not _health(config):
            pid_file.unlink(missing_ok=True)
            print("Gateway stopped")
            return 0
        time.sleep(0.1)
    print("Gateway did not stop within two seconds", file=sys.stderr)
    return 1


def _route(config: Any, name: str) -> Any:
    try:
        return config.routes[name]
    except KeyError as exc:
        raise ConfigError(f"Unknown configured route: {name}") from exc


def _validate_brief(path: Path, task_name: str) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Brief not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Brief contains invalid JSON: {exc}") from exc
    required = {"schema_version", "task_name", "status", "outcome", "scope", "checks", "stop_when"}
    missing = sorted(required - set(data)) if isinstance(data, dict) else sorted(required)
    if missing:
        raise ConfigError(f"Brief is missing required fields: {', '.join(missing)}")
    if data["schema_version"] != 1:
        raise ConfigError("Brief schema_version must be 1")
    if data["task_name"] != task_name:
        raise ConfigError("Brief task_name does not match")
    if data["status"] != "pending":
        raise ConfigError("Brief status must be pending")
    for field in ("scope", "checks", "stop_when"):
        if not isinstance(data[field], list):
            raise ConfigError(f"Brief {field} must be an array")


def _parse_header_env(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ConfigError("--header-env values must use HEADER=ENV")
        header, env_name = value.split("=", 1)
        if not header.strip() or not env_name.strip():
            raise ConfigError("--header-env values must use non-empty HEADER=ENV")
        result[header.strip()] = env_name.strip()
    return result


def _parse_key_command(args: Any) -> list[str] | None:
    if args.api_key_command and args.api_key_command_json:
        raise ConfigError("Use only one of --api-key-command and --api-key-command-json")
    if not args.api_key_command_json:
        return args.api_key_command
    try:
        value = json.loads(args.api_key_command_json)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"--api-key-command-json is invalid JSON: {exc}") from exc
    if not isinstance(value, list) or not value or not all(isinstance(part, str) and part for part in value):
        raise ConfigError("--api-key-command-json must be a non-empty JSON string array")
    return value


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "providers":
            presets = load_presets()
            if args.json:
                print(json.dumps(presets, indent=2, ensure_ascii=False))
            else:
                for name, preset in presets.items():
                    print(f"{name:20} {preset['protocol']:20} {preset['label']}")
            return 0

        if args.command == "configure":
            path = save_route(
                args.config,
                name=args.route,
                provider=args.provider,
                model=args.model,
                base_url=args.base_url,
                api_key_env=args.api_key_env,
                api_key_command=_parse_key_command(args),
                brief_mode=args.brief_mode,
                auth=args.auth,
                header_env=_parse_header_env(args.header_env),
                drop_request_fields=args.drop_request_field,
            )
            load_config(path)
            print(f"Configured route {args.route} in {path}")
            return 0

        if args.command == "routes":
            config = load_config(args.config)
            data = {
                name: {
                    "provider": route.provider,
                    "model": route.model,
                    "protocol": route.protocol,
                    "brief_mode": route.brief_mode,
                    "agent_type": agent_name(name),
                    "capabilities": route.capabilities,
                    "limitations": route.limitations,
                }
                for name, route in config.routes.items()
            }
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                for name, item in data.items():
                    print(f"{name:20} {item['protocol']:20} {item['model']}  [{item['agent_type']}]")
            return 0

        if args.command == "validate":
            config = load_config(args.config)
            names = [args.route] if args.route else list(config.routes)
            for name in names:
                route = _route(config, name)
                print(f"OK config route={name} provider={route.provider} protocol={route.protocol}")
                if args.live:
                    result = probe_route(route, include_tools=args.tools)
                    output_types = [item.get("type") for item in result.get("output", [])] if result.get("object") == "response" else []
                    if args.tools and not any(kind in {"function_call", "custom_tool_call"} for kind in output_types):
                        raise ProtocolError(f"Route {name} returned no tool call during the tool probe")
                    if not args.tools and result.get("object") == "response" and "message" not in output_types:
                        raise ProtocolError(f"Route {name} returned no text message during the text probe")
                    print(f"OK live route={name} status={result.get('status', 'completed')} output={output_types or 'provider-native'}")
            return 0

        if args.command == "gateway":
            config = load_config(args.config)
            if args.gateway_command == "serve":
                logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
                serve(config)
                return 0
            if args.gateway_command == "start":
                return _gateway_start(config)
            if args.gateway_command == "status":
                health = _health(config)
                if health:
                    print(json.dumps(health, indent=2, ensure_ascii=False))
                    return 0
                print("Gateway is not running", file=sys.stderr)
                return 1
            if args.gateway_command == "stop":
                return _gateway_stop(config)

        if args.command == "codex":
            config = load_config(args.config)
            route = _route(config, args.route)
            if args.codex_command == "preview":
                print(render(config, route))
                return 0
            if args.codex_command == "uninstall":
                result = uninstall(config, route, apply=args.apply)
                if not args.apply:
                    print("Dry run only. Re-run with --apply to remove the managed provider block and Agent file:")
                else:
                    print("Removed the managed route and Agent file. The shared Skill was preserved. Restart Codex.")
                print(f"config: {result.config_file}\nagent:  {result.agent_file}\nskill:  {result.skill_dir} (preserved)")
                return 0
            source_skill = Path(__file__).resolve().parents[2]
            result = install(config, route, source_skill, apply=args.apply)
            if not args.apply:
                print("Dry run only. Re-run with --apply to write these targets:")
            else:
                print("Installed Codex External Executor. Restart Codex before first use.")
            print(f"config: {result.config_file}\nagent:  {result.agent_file}\nskill:  {result.skill_dir}")
            return 0

        if args.command == "brief" and args.brief_command == "validate":
            _validate_brief(args.path, args.task_name)
            print(f"OK brief {args.path}")
            return 0
    except (ConfigError, ProtocolError, UpstreamError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2
