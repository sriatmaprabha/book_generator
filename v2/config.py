"""
Configuration loader — reads config.yaml and builds per-agent model instances.

Supports ${ENV_VAR} interpolation in string values.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


# ── Config schema ───────────────────────────────────────────────────────────

class AgentModelConfig(BaseModel):
    """Model settings for a single agent."""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    max_tokens: int = 8192


class McpSourceConfig(BaseModel):
    name: str
    url: str
    transport: str = "streamable-http"


class WorkflowSettings(BaseModel):
    max_stage_retries: int = 2
    min_chapter_words: int = 2000
    max_chapter_words: int = 5000
    min_section_paragraphs: int = 3
    output_dir: str = "output"
    writer_batch_size: int = 3
    parallel_research: bool = True
    parallel_editing: bool = True


class AppConfig(BaseModel):
    """Top-level application configuration."""
    defaults: AgentModelConfig = Field(default_factory=AgentModelConfig)
    agents: Dict[str, AgentModelConfig] = Field(default_factory=dict)
    mcp_sources: List[McpSourceConfig] = Field(default_factory=list)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)


# ── Env interpolation ──────────────────────────────────────────────────────

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _interpolate_env(value: Any) -> Any:
    """Replace ${ENV_VAR} placeholders in string values."""
    if isinstance(value, str):
        def _replacer(match: re.Match) -> str:
            env_name = match.group(1)
            env_val = os.environ.get(env_name, "")
            return env_val
        return _ENV_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


# ── Loader ─────────────────────────────────────────────────────────────────

_CONFIG_FILENAME = "config.yaml"
_loaded_config: Optional[AppConfig] = None


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load and cache configuration from YAML."""
    global _loaded_config
    if _loaded_config is not None:
        return _loaded_config

    if config_path is None:
        config_path = str(Path(__file__).parent / _CONFIG_FILENAME)

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    raw = _interpolate_env(raw)
    _loaded_config = AppConfig.model_validate(raw)
    return _loaded_config


def reload_config(config_path: Optional[str] = None) -> AppConfig:
    """Force-reload configuration (useful after env changes)."""
    global _loaded_config
    _loaded_config = None
    return load_config(config_path)


def get_agent_config(agent_name: str, config: Optional[AppConfig] = None) -> AgentModelConfig:
    """
    Return the resolved config for a named agent.
    Agent-level values override defaults; missing fields fall back to defaults.
    """
    cfg = config or load_config()
    defaults = cfg.defaults
    agent_cfg = cfg.agents.get(agent_name, AgentModelConfig())

    return AgentModelConfig(
        model=agent_cfg.model or defaults.model,
        base_url=agent_cfg.base_url or defaults.base_url,
        api_key=agent_cfg.api_key or defaults.api_key,
        max_tokens=agent_cfg.max_tokens if agent_cfg.max_tokens != 8192 else defaults.max_tokens,
    )


# ── Model factory ──────────────────────────────────────────────────────────

def build_agent_model(agent_name: str, config: Optional[AppConfig] = None):
    """
    Build an OpenAI-compatible model instance for the named agent.
    Uses agno's OpenAILike so any OpenAI-compatible endpoint works
    (NVIDIA, OpenRouter, local vLLM, etc.).
    """
    from agno.models.openai import OpenAILike

    acfg = get_agent_config(agent_name, config)
    return OpenAILike(
        id=acfg.model,
        api_key=acfg.api_key,
        base_url=acfg.base_url,
        max_tokens=acfg.max_tokens,
    )
