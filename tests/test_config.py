from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "external-model-executor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from external_executor_lib.cli import main  # noqa: E402
from external_executor_lib.codex_install import _replace_managed_block  # noqa: E402
from external_executor_lib.config import ConfigError, RouteConfig, load_config, save_route  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_save_and_load_custom_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_route(
                path,
                name="relay-one",
                provider="custom-openai-chat",
                model="vendor/model",
                base_url="https://relay.example/v1/",
                api_key_env="RELAY_KEY",
                api_key_command=None,
                brief_mode="always",
            )
            config = load_config(path)
            route = config.routes["relay-one"]
            self.assertEqual(route.protocol, "openai_chat")
            self.assertEqual(route.base_url, "https://relay.example/v1")
            self.assertEqual(route.api_key_env, "RELAY_KEY")
            self.assertEqual(route.brief_mode, "always")

    def test_rejects_non_loopback_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "server": {"host": "0.0.0.0", "port": 8787},
                        "routes": {"openai": {"provider": "openai", "model": "test"}},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_custom_provider_requires_base_url_without_overwriting_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_route(
                path,
                name="valid",
                provider="openai",
                model="test-model",
                base_url=None,
                api_key_env="OPENAI_API_KEY",
                api_key_command=None,
                brief_mode="off",
            )
            before = path.read_text(encoding="utf-8")
            with self.assertRaises(ConfigError):
                save_route(
                    path,
                    name="broken",
                    provider="custom-responses",
                    model="model",
                    base_url=None,
                    api_key_env="KEY",
                    api_key_command=None,
                    brief_mode="auto",
                )
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_managed_config_block_is_idempotent(self) -> None:
        block = "# BEGIN codex-external-executor:r\nvalue = 1\n# END codex-external-executor:r\n"
        first, changed = _replace_managed_block("model = \"main\"\n", "r", block)
        self.assertTrue(changed)
        second, changed_again = _replace_managed_block(first, "r", block)
        self.assertFalse(changed_again)
        self.assertEqual(first, second)

    def test_codex_install_writes_only_expected_temp_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "external.json"
            save_route(
                config_path,
                name="deepseek",
                provider="deepseek",
                model="deepseek-test",
                base_url=None,
                api_key_env="DEEPSEEK_API_KEY",
                api_key_command=None,
                brief_mode="auto",
            )
            codex_home = root / "codex-home"
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                result = main(
                    [
                        "codex",
                        "install",
                        "--config",
                        str(config_path),
                        "--route",
                        "deepseek",
                        "--apply",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue((codex_home / "config.toml").is_file())
            self.assertTrue((codex_home / "agents" / "external-executor-deepseek.toml").is_file())
            self.assertTrue((codex_home / "skills" / "external-model-executor" / "SKILL.md").is_file())
            self.assertNotIn("DEEPSEEK_API_KEY=", (codex_home / "config.toml").read_text(encoding="utf-8"))

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                uninstall_result = main(
                    [
                        "codex",
                        "uninstall",
                        "--config",
                        str(config_path),
                        "--route",
                        "deepseek",
                        "--apply",
                    ]
                )
            self.assertEqual(uninstall_result, 0)
            self.assertFalse((codex_home / "agents" / "external-executor-deepseek.toml").exists())
            self.assertNotIn("codex-external-executor:deepseek", (codex_home / "config.toml").read_text(encoding="utf-8"))
            self.assertTrue((codex_home / "skills" / "external-model-executor" / "SKILL.md").is_file())

    def test_custom_header_can_supply_auth_without_bearer_key(self) -> None:
        route = RouteConfig(
            name="relay",
            provider="custom",
            model="model",
            protocol="responses",
            base_url="http://127.0.0.1:9999",
            api_key_env=None,
            auth="none",
            header_env={"X-Relay-Key": "RELAY_HEADER_KEY"},
        )
        with patch.dict(os.environ, {"RELAY_HEADER_KEY": "test-value"}):
            headers = route.request_headers()
        self.assertEqual(headers["X-Relay-Key"], "test-value")
        self.assertNotIn("Authorization", headers)


if __name__ == "__main__":
    unittest.main()
