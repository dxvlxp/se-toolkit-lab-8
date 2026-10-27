"""Test config resolution without starting an agent or exposing real secrets."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "lab8_entrypoint", PROJECT / "entrypoint.py"
)
assert spec and spec.loader
entry: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


def template() -> dict[str, Any]:
    return json.loads((PROJECT / "config.example.json").read_text())


def environment() -> dict[str, str]:
    return {
        "LLM_API_KEY": "test-llm-key",
        "LLM_API_BASE_URL": "http://qwen-code-api:8080/v1",
        "LLM_API_MODEL": "coder-model",
        "LMS_API_KEY": "test-backend-key",
        "NANOBOT_ACCESS_KEY": "test-web-key",
        "NANOBOT_LMS_BACKEND_URL": "http://backend:8000",
        "NANOBOT_VICTORIALOGS_URL": "http://victorialogs:9428",
        "NANOBOT_VICTORIATRACES_URL": "http://victoriatraces:10428",
    }


def test_runtime_values_and_mcp_environment(tmp_path: Path) -> None:
    config = entry.resolve_config(template(), environment(), tmp_path)
    assert config["providers"]["custom"]["apiKey"] == "test-llm-key"
    assert config["providers"]["custom"]["apiBase"] == "http://qwen-code-api:8080/v1"
    servers = config["tools"]["mcpServers"]
    assert set(servers) == {"lms", "obs", "webchat"}
    assert servers["lms"]["env"]["NANOBOT_LMS_API_KEY"] == "test-backend-key"
    assert (
        servers["obs"]["env"]["NANOBOT_VICTORIATRACES_URL"]
        == "http://victoriatraces:10428"
    )
    assert servers["webchat"]["env"]["NANOBOT_UI_RELAY_TOKEN"] == "test-web-key"
    assert config["channels"]["webchat"]["relayHost"] == "127.0.0.1"


def test_template_is_not_mutated(tmp_path: Path) -> None:
    source = template()
    entry.resolve_config(source, environment(), tmp_path)
    assert source == template()


def test_unrelated_custom_settings_are_preserved(tmp_path: Path) -> None:
    source = template()
    source["agents"]["defaults"]["temperature"] = 0.25
    assert (
        entry.resolve_config(source, environment(), tmp_path)["agents"]["defaults"][
            "temperature"
        ]
        == 0.25
    )


def test_bare_stage_has_no_live_tools(tmp_path: Path) -> None:
    config = entry.resolve_config(template(), {"LLM_API_KEY": "test"}, tmp_path, "bare")
    assert config["tools"]["mcpServers"] == {}
    assert not config["channels"]["webchat"]["enabled"]


def test_lms_stage_has_only_lms_tools(tmp_path: Path) -> None:
    config = entry.resolve_config(template(), environment(), tmp_path, "lms")
    assert set(config["tools"]["mcpServers"]) == {"lms"}


@pytest.mark.parametrize(
    "name", ["LLM_API_KEY", "NANOBOT_ACCESS_KEY", "NANOBOT_VICTORIALOGS_URL"]
)
def test_missing_credentials_or_services_fail_clearly(
    tmp_path: Path, name: str
) -> None:
    env = environment()
    env.pop(name)
    with pytest.raises(ValueError, match=name):
        entry.resolve_config(template(), env, tmp_path)


def test_port_override_is_validated(tmp_path: Path) -> None:
    env = environment()
    env["NANOBOT_WEBCHAT_CONTAINER_PORT"] = "70000"
    with pytest.raises(ValueError, match="port"):
        entry.resolve_config(template(), env, tmp_path)


def test_private_config_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("old config")
    path.chmod(0o644)
    entry.write_config({"secret": "test"}, path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == {"secret": "test"}


def test_config_is_accepted_by_pinned_framework(tmp_path: Path) -> None:
    from nanobot.config.schema import Config

    resolved = entry.resolve_config(template(), environment(), tmp_path)
    config = Config.model_validate(resolved)
    assert config.agents.defaults.provider == "custom"
    assert set(config.tools.mcp_servers) == {"lms", "obs", "webchat"}


def test_webchat_plugin_is_discoverable() -> None:
    from nanobot.channels.registry import discover_all

    assert "webchat" in discover_all()
