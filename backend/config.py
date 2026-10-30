"""Loads settings from .env. Never prints or logs the API key."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

DEFAULT_TIMEOUT_S = 60
_REQUIRED = ["GEMINI_API_KEY", "AGENT_MODEL", "SIM_MODEL", "JUDGE_MODEL", "RPM_LIMIT"]


class ConfigError(Exception):
    """A required setting is missing or invalid (message names variables only)."""


@dataclass(frozen=True)
class Config:
    gemini_api_key: str = field(repr=False)
    agent_model: str
    sim_model: str
    judge_model: str
    rpm_limit: int
    request_timeout_s: int = DEFAULT_TIMEOUT_S


def _get(name: str) -> str:
    return os.environ.get(name, "").strip()


def get_api_key() -> str:
    """Only the key, so list_models works before model names are filled in."""
    load_dotenv()
    key = _get("GEMINI_API_KEY")
    if not key:
        raise ConfigError("GEMINI_API_KEY is missing or blank. Set it in .env.")
    return key


def _positive_int(name: str, raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        raise ConfigError(f"{name} must be a positive integer.")
    return value


def get_config() -> Config:
    load_dotenv()
    missing = [name for name in _REQUIRED if not _get(name)]
    if missing:
        raise ConfigError(
            "Missing or blank in .env: " + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )
    timeout = _get("LLM_TIMEOUT_S")
    return Config(
        gemini_api_key=_get("GEMINI_API_KEY"),
        agent_model=_get("AGENT_MODEL"),
        sim_model=_get("SIM_MODEL"),
        judge_model=_get("JUDGE_MODEL"),
        rpm_limit=_positive_int("RPM_LIMIT", _get("RPM_LIMIT")),
        request_timeout_s=(
            _positive_int("LLM_TIMEOUT_S", timeout) if timeout else DEFAULT_TIMEOUT_S
        ),
    )
