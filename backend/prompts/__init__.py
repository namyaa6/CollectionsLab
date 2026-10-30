"""Loads versioned agent prompts from backend/prompts/vN.yaml."""
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    self_check: bool = False  # v4+: review each draft reply before it is spoken
    self_check_prompt: str = ""


def load_prompt(version: str, directory: Path = PROMPTS_DIR) -> Prompt:
    if not re.fullmatch(r"v\d+", version):
        raise ValueError(f"prompt version must look like 'v1', got {version!r}")
    path = directory / f"{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no prompt file for version {version!r}: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    system = str(data.get("system", "")).strip()
    if not system:
        raise ValueError(f"{path.name} has no 'system' text")
    self_check = data.get("self_check", False)
    if not isinstance(self_check, bool):
        raise ValueError(f"{path.name}: self_check must be true or false, got {self_check!r}")
    check_prompt = str(data.get("self_check_prompt", "")).strip()
    if self_check and not check_prompt:
        raise ValueError(f"{path.name} has self_check: true but no 'self_check_prompt' text")
    return Prompt(version=version, system=system, self_check=self_check,
                  self_check_prompt=check_prompt)


def prompt_file_hash(version: str, directory: Path = PROMPTS_DIR) -> str:
    """sha256 of the prompt file, so an edited vN.yaml is never mixed into an older run."""
    return hashlib.sha256((directory / f"{version}.yaml").read_bytes()).hexdigest()
