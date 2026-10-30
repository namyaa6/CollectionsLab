"""Shared types for the LLM client and the fake client.

A message is a dict:
  {"role": "user", "text": "..."}
  {"role": "model", "raw": <genai Content>}    # replayed unchanged (keeps thought signatures)
  {"role": "model", "text": "...", "tool_calls": [{"name": ..., "args": {...}}]}
  {"role": "tool", "results": [{"name": ..., "response": {...}}]}
"""
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from google.genai import types as genai_types


class LLMError(Exception):
    """Base class for LLM client errors."""


class QuotaExhaustedError(LLMError):
    """The daily quota is used up; retrying will not help."""


class LLMResponseError(LLMError):
    """The model reply could not be used (e.g. invalid structured output)."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema for the arguments


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    parsed: Any = None  # Pydantic object when response_schema was given
    raw_content: Any = None  # genai Content exactly as returned; replay unchanged
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    finish_reason: str = "STOP"

    @property
    def cacheable(self) -> bool:
        """Failed, empty, blocked or truncated replies are never cached."""
        return self.finish_reason == "STOP" and bool(self.text or self.tool_calls)

    def to_entry(self) -> dict:
        raw = self.raw_content
        return {
            "text": self.text,
            "tool_calls": [{"name": c.name, "args": c.args} for c in self.tool_calls],
            # model_dump_json base64-encodes signature bytes; validate_json reverses it
            "raw_content": raw.model_dump_json(exclude_none=True) if raw else None,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "finish_reason": self.finish_reason,
        }

    @classmethod
    def from_entry(cls, entry: dict) -> "LLMResponse":
        raw = entry.get("raw_content")
        return cls(
            text=entry["text"],
            tool_calls=[ToolCall(c["name"], c["args"]) for c in entry["tool_calls"]],
            raw_content=genai_types.Content.model_validate_json(raw) if raw else None,
            latency_ms=entry["latency_ms"],
            input_tokens=entry["input_tokens"],
            output_tokens=entry["output_tokens"],
            cached=True,
            finish_reason=entry["finish_reason"],
        )


def normalize_messages(messages: list[dict]) -> list[dict]:
    """JSON-safe copy of messages (raw Content becomes its JSON string); used for cache keys."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("raw") is not None:
            m["raw"] = m["raw"].model_dump_json(exclude_none=True)
        if "tool_calls" in m:
            m["tool_calls"] = [
                c if isinstance(c, dict) else {"name": c.name, "args": c.args}
                for c in m["tool_calls"]
            ]
        out.append(m)
    return json.loads(json.dumps(out, default=str))


def parse_structured(text: str, schema: Optional[type]) -> Any:
    """Validate JSON text against a Pydantic model; raise LLMResponseError on failure."""
    try:
        return schema.model_validate_json(text)
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        raise LLMResponseError(f"Reply is not valid {schema.__name__} JSON: {exc}") from exc
