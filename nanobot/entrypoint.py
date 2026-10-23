"""Resolve deployment credentials into local config and exec the Nanobot CLI."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value or value.startswith(("<", "YOUR_")) or "${" in value:
        raise ValueError(f"Set {name} to a real value in the deployment environment")
    return value


def port(env: Mapping[str, str], name: str, fallback: int) -> int:
    value = int(env.get(name, str(fallback)))
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be a port between 1 and 65535")
    return value


def url(value: str, name: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            f"{name} must be an HTTP(S) URL without credentials or query parameters"
        )
    return value.rstrip("/")


def resolve_config(
    template: dict[str, Any],
    env: Mapping[str, str],
    workspace: Path,
    stage: str = "full",
) -> dict[str, Any]:
    config = deepcopy(template)
    defaults = config.setdefault("agents", {}).setdefault("defaults", {})
    defaults.update(workspace=str(workspace.resolve()), provider="custom")
    defaults["model"] = env.get("LLM_API_MODEL") or defaults.get("model", "coder-model")
    custom = config.setdefault("providers", {}).setdefault("custom", {})
    custom["apiKey"] = required(env, "LLM_API_KEY")
    custom["apiBase"] = url(
        env.get("LLM_API_BASE_URL") or custom.get("apiBase", ""), "LLM_API_BASE_URL"
    )
    gateway = config.setdefault("gateway", {})
    gateway.update(
        host=env.get("NANOBOT_GATEWAY_CONTAINER_ADDRESS", "0.0.0.0"),
        port=port(env, "NANOBOT_GATEWAY_CONTAINER_PORT", 18790),
    )
    tools = config.setdefault("tools", {})
    servers = tools.setdefault("mcpServers", {})
    channels = config.setdefault("channels", {})
    webchat = channels.setdefault("webchat", {})
    webchat["enabled"] = stage == "full"
    if stage == "bare":
        tools["mcpServers"] = {}
        return config
    backend_url = url(
        env.get("NANOBOT_LMS_BACKEND_URL", "http://localhost:42002"),
        "NANOBOT_LMS_BACKEND_URL",
    )
    backend_key = env.get("NANOBOT_LMS_API_KEY") or env.get("LMS_API_KEY", "")
    lms_env = {
        "NANOBOT_LMS_API_KEY": required(
            {"NANOBOT_LMS_API_KEY": backend_key}, "NANOBOT_LMS_API_KEY"
        ),
        "NANOBOT_LMS_BACKEND_URL": backend_url,
    }
    lms = servers.setdefault("lms", {})
    lms.update(command=sys.executable, args=["-m", "mcp_lms"])
    lms.setdefault("env", {}).update(lms_env)
    if stage == "lms":
        tools["mcpServers"] = {"lms": lms}
        return config
    access_key = required(env, "NANOBOT_ACCESS_KEY")
    webchat.update(
        host=env.get("NANOBOT_WEBCHAT_CONTAINER_ADDRESS", "0.0.0.0"),
        port=port(env, "NANOBOT_WEBCHAT_CONTAINER_PORT", 8765),
        allowFrom=["*"],
    )
    relay_port = port(env, "NANOBOT_UI_RELAY_PORT", 8766)
    # The relay is internal to this container; it is not published through Caddy.
    webchat.update(relayHost="127.0.0.1", relayPort=relay_port)
    obs = servers.setdefault("obs", {})
    obs.update(command=sys.executable, args=["-m", "mcp_obs"])
    obs.setdefault("env", {}).update(
        {
            "NANOBOT_VICTORIALOGS_URL": url(
                required(env, "NANOBOT_VICTORIALOGS_URL"), "NANOBOT_VICTORIALOGS_URL"
            ),
            "NANOBOT_VICTORIATRACES_URL": url(
                required(env, "NANOBOT_VICTORIATRACES_URL"),
                "NANOBOT_VICTORIATRACES_URL",
            ),
        }
    )
    ui = servers.setdefault("webchat", {})
    ui.update(command=sys.executable, args=["-m", "mcp_webchat"])
    ui.setdefault("env", {}).update(
        {
            "NANOBOT_UI_RELAY_URL": f"http://127.0.0.1:{relay_port}",
            "NANOBOT_UI_RELAY_TOKEN": env.get("NANOBOT_UI_RELAY_TOKEN") or access_key,
        }
    )
    return config


def write_config(config: dict[str, Any], destination: Path) -> None:
    """Create a private file without exposing secrets during the write."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(destination, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["bare", "lms", "full"], default="full")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run", choices=["agent", "gateway"], default="gateway")
    parser.add_argument("--session", default="cli:lab8")
    parser.add_argument("--message", "-m")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    source = project / "config.json"
    if not source.exists():
        source = project / "config.example.json"
    try:
        config = resolve_config(
            json.loads(source.read_text()),
            os.environ,
            project / "workspace",
            args.stage,
        )
        destination = project / "config.resolved.json"
        write_config(config, destination)
        print(f"Using config: {destination}", flush=True)
        if args.prepare_only:
            return 0
        command = [
            "nanobot",
            args.run,
            "--config",
            str(destination),
            "--workspace",
            str(project / "workspace"),
        ]
        if args.run == "agent":
            command.extend(["--logs", "--session", args.session])
            if args.message:
                command.extend(["--message", args.message])
        os.execvp(command[0], command)
    except (ValueError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
