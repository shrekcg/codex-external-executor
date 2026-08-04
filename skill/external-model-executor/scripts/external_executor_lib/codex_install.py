"""Render and install the Codex provider, agent profile, and Skill."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import hashlib
from datetime import datetime, timezone
from typing import NamedTuple

from .config import AppConfig, ConfigError, RouteConfig


class InstallResult(NamedTuple):
    config_file: Path
    agent_file: Path
    skill_dir: Path
    changed: bool


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def provider_id(route_name: str) -> str:
    return "external_executor_" + route_name.replace("-", "_")


def agent_name(route_name: str) -> str:
    return f"External Executor - {route_name}"


def provider_block(config: AppConfig, route: RouteConfig) -> str:
    identifier = provider_id(route.name)
    return (
        f"# BEGIN codex-external-executor:{route.name}\n"
        f"[model_providers.{identifier}]\n"
        f'name = "External Executor ({route.name})"\n'
        f'base_url = "http://{config.host}:{config.port}/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n"
        f"# END codex-external-executor:{route.name}\n"
    )


def _brief_instructions(route: RouteConfig) -> str:
    if route.brief_mode == "off":
        return "Do not look for an external task brief; use only the parent task message."
    read_condition = "Read the brief before starting." if route.brief_mode == "always" else (
        "Read the brief only when the parent task message is empty, missing, or clearly incomplete."
    )
    return f"""External task-brief fallback: {read_condition} The path is
`<cwd>/work/external-model-briefs/<task-name-leaf>.json`, where `task-name-leaf`
is the final path segment of the Task name in the collaboration message. Accept
the file only when `schema_version` is 1, `task_name` exactly matches that leaf,
and `status` is `pending`. Use only the matching brief; never search for another
brief. Stop and report the mismatch when validation fails."""


def agent_toml(route: RouteConfig) -> str:
    description = (
        f"Explicit external-model executor using route {route.name} ({route.provider}). "
        "The parent Agent retains scope, permissions, verification, and final acceptance."
    )
    developer = f"""You are {agent_name(route.name)}, a Codex native sub-agent whose model
requests are routed through Codex External Executor.

Complete the parent's bounded task inside the inherited workspace and permission
boundary. Preserve unrelated work. Do not expose credentials or inspect secret
files. Do not spawn sub-agents. If the task is ambiguous, consequential, outside
scope, or cannot be verified, stop and return the decision to the parent.

{_brief_instructions(route)}

Report what changed or what evidence was found, files or sources inspected,
checks run and results, and remaining risks or blockers.
"""
    escaped_description = description.replace('"', '\\"')
    return (
        f'name = "{agent_name(route.name)}"\n'
        f'description = "{escaped_description}"\n'
        f'model_provider = "{provider_id(route.name)}"\n'
        f'model = "{route.name}"\n'
        'model_reasoning_effort = "medium"\n'
        'sandbox_mode = "workspace-write"\n\n'
        'developer_instructions = """\n'
        + developer
        + '\n"""\n'
    )


def _replace_managed_block(text: str, route_name: str, block: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(?ms)^# BEGIN codex-external-executor:{re.escape(route_name)}\n.*?"
        rf"^# END codex-external-executor:{re.escape(route_name)}\n?"
    )
    if pattern.search(text):
        updated = pattern.sub(block, text)
    else:
        separator = "" if not text or text.endswith("\n\n") else "\n"
        updated = text + separator + block
    return updated, updated != text


def _remove_managed_block(text: str, route_name: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(?ms)^# BEGIN codex-external-executor:{re.escape(route_name)}\n.*?"
        rf"^# END codex-external-executor:{re.escape(route_name)}\n?"
    )
    updated = pattern.sub("", text)
    return updated, updated != text


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _backup_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render(config: AppConfig, route: RouteConfig) -> str:
    return provider_block(config, route) + "\n# Agent file\n" + agent_toml(route)


def install(config: AppConfig, route: RouteConfig, source_skill: Path, apply: bool) -> InstallResult:
    home = codex_home()
    config_file = home / "config.toml"
    agent_file = home / "agents" / f"external-executor-{route.name}.toml"
    skill_dir = home / "skills" / "external-model-executor"
    existing = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    updated, config_changed = _replace_managed_block(existing, route.name, provider_block(config, route))
    desired_agent = agent_toml(route)
    agent_changed = not agent_file.exists() or agent_file.read_text(encoding="utf-8") != desired_agent
    source_skill = source_skill.resolve()
    if not (source_skill / "SKILL.md").is_file():
        raise ConfigError(f"Skill source is invalid: {source_skill}")
    skill_changed = not skill_dir.exists() or (
        source_skill != skill_dir.resolve() and _tree_digest(source_skill) != _tree_digest(skill_dir)
    )
    changed = config_changed or agent_changed or skill_changed
    if not apply:
        return InstallResult(config_file, agent_file, skill_dir, changed)
    home.mkdir(parents=True, exist_ok=True)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    if config_file.exists() and config_changed:
        backup = config_file.with_name(f"config.toml.external-executor.{_backup_suffix()}.bak")
        shutil.copy2(config_file, backup)
    config_file.write_text(updated, encoding="utf-8")
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(desired_agent, encoding="utf-8")
    if source_skill != skill_dir.resolve() and skill_changed:
        if skill_dir.exists():
            backup = skill_dir.with_name(f"external-model-executor.{_backup_suffix()}.bak")
            shutil.copytree(skill_dir, backup, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.rmtree(skill_dir)
        shutil.copytree(source_skill, skill_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return InstallResult(config_file, agent_file, skill_dir, changed)


def uninstall(config: AppConfig, route: RouteConfig, apply: bool) -> InstallResult:
    home = codex_home()
    config_file = home / "config.toml"
    agent_file = home / "agents" / f"external-executor-{route.name}.toml"
    skill_dir = home / "skills" / "external-model-executor"
    existing = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    updated, config_changed = _remove_managed_block(existing, route.name)
    changed = config_changed or agent_file.exists()
    if not apply:
        return InstallResult(config_file, agent_file, skill_dir, changed)
    if config_file.exists() and config_changed:
        backup = config_file.with_name(f"config.toml.external-executor.{_backup_suffix()}.bak")
        shutil.copy2(config_file, backup)
        config_file.write_text(updated, encoding="utf-8")
    if agent_file.exists():
        backup = agent_file.with_name(f"{agent_file.name}.{_backup_suffix()}.bak")
        shutil.copy2(agent_file, backup)
        agent_file.unlink()
    return InstallResult(config_file, agent_file, skill_dir, changed)
