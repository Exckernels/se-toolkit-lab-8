"""Resolve Docker env vars into nanobot config, then exec `nanobot gateway`."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _app_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _apply_env_overrides(cfg: dict) -> None:
    """Mutate cfg in place from well-known Compose env vars."""

    llm_key = os.environ.get("LLM_API_KEY", "").strip()
    llm_base = os.environ.get("LLM_API_BASE_URL", "").strip()
    llm_model = os.environ.get("LLM_API_MODEL", "").strip()

    if llm_key or llm_base:
        prov = cfg.setdefault("providers", {}).setdefault("openai", {})
        if llm_key:
            prov["apiKey"] = llm_key
        if llm_base:
            prov["apiBase"] = llm_base

    if llm_model:
        cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = llm_model

    gw_host = os.environ.get("NANOBOT_GATEWAY_CONTAINER_ADDRESS", "").strip()
    gw_port = os.environ.get("NANOBOT_GATEWAY_CONTAINER_PORT", "").strip()
    if gw_host or gw_port:
        gw = cfg.setdefault("gateway", {})
        if gw_host:
            gw["host"] = gw_host
        if gw_port:
            gw["port"] = int(gw_port)

    # Optional: webchat plugin (Part B) often reads bind settings from channel config.
    wch_host = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_ADDRESS", "").strip()
    wch_port = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_PORT", "").strip()
    channels = cfg.get("channels")
    if isinstance(channels, dict):
        webchat = channels.get("webchat")
        if isinstance(webchat, dict) and webchat.get("enabled") is True:
            if wch_host:
                webchat["host"] = wch_host
            if wch_port:
                webchat["port"] = int(wch_port)

    backend_url = os.environ.get("NANOBOT_LMS_BACKEND_URL", "").strip()
    backend_key = os.environ.get("NANOBOT_LMS_API_KEY", "").strip()
    mcp = (
        cfg.get("tools", {})
        .get("mcpServers", {})
        .get("lms")
    )
    if isinstance(mcp, dict):
        env = mcp.setdefault("env", {})
        if backend_url:
            env["NANOBOT_LMS_BACKEND_URL"] = backend_url
        if backend_key:
            env["NANOBOT_LMS_API_KEY"] = backend_key

    workspace = os.environ.get("NANOBOT_WORKSPACE", "").strip()
    if workspace:
        cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = workspace


def main() -> None:
    app_dir = _app_dir()
    src = app_dir / "config.json"
    if not src.is_file():
        raise SystemExit(f"Missing config: {src}")

    cfg = _load_config(src)
    _apply_env_overrides(cfg)

    resolved = app_dir / "config.resolved.json"
    _write_config(resolved, cfg)

    workspace_raw = os.environ.get("NANOBOT_WORKSPACE", "").strip()
    if workspace_raw:
        workspace_path = Path(workspace_raw).expanduser().resolve()
    else:
        workspace_path = (app_dir / "workspace").resolve()

    workspace_path.mkdir(parents=True, exist_ok=True)

    os.execvp(
        "nanobot",
        [
            "nanobot",
            "gateway",
            "--config",
            str(resolved),
            "--workspace",
            str(workspace_path),
        ],
    )


if __name__ == "__main__":
    main()
