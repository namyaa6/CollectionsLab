"""Scripted fake LLM client for tests: no network, no API key."""
from typing import Callable, Optional, Union

from backend.llm.types import LLMResponse, ToolCall, ToolSpec, parse_structured

ScriptItem = Union[LLMResponse, Callable[[dict], LLMResponse]]


def text_reply(text: str, **kwargs) -> LLMResponse:
    return LLMResponse(text=text, latency_ms=10, input_tokens=5, output_tokens=5, **kwargs)


def tool_reply(name: str, args: Optional[dict] = None, text: str = "") -> LLMResponse:
    return LLMResponse(text=text, tool_calls=[ToolCall(name, args or {})],
                       latency_ms=10, input_tokens=5, output_tokens=5)


class FakeLLMClient:
    """Returns scripted replies in order. `calls` records every request."""

    def __init__(self, script: list[ScriptItem]):
        self._script = list(script)
        self.calls: list[dict] = []

    def generate(self, model: str, messages: list[dict], system: Optional[str] = None,
                 tools: Optional[list[ToolSpec]] = None, temperature: float = 0.0,
                 json_mode: bool = False, response_schema: Optional[type] = None,
                 use_cache: bool = True, cache_salt: Optional[str] = None) -> LLMResponse:
        request = {"model": model, "messages": list(messages), "system": system, "tools": tools,
                   "temperature": temperature, "json_mode": json_mode,
                   "response_schema": response_schema, "use_cache": use_cache,
                   "cache_salt": cache_salt}
        self.calls.append(request)
        if not self._script:
            raise AssertionError(
                f"FakeLLMClient script exhausted: call #{len(self.calls)} had no scripted reply")
        item = self._script.pop(0)
        resp = item(request) if callable(item) else item
        if response_schema and resp.parsed is None and resp.text:
            resp.parsed = parse_structured(resp.text, response_schema)
        return resp
