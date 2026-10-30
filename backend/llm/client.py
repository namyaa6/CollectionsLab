"""The one LLM wrapper: text, function calling, structured output.

Disk cache -> rate limiter -> API call with retries. Callers never import genai.
"""
import logging
import time
from typing import Any, Callable, Optional, Protocol

from google import genai
from google.genai import types as gt

from backend.config import Config
from backend.llm.cache import DiskCache, make_key
from backend.llm.retry import RateLimiter, backoff_delay, is_daily_quota, is_retryable
from backend.llm.types import (
    LLMResponse, LLMResponseError, QuotaExhaustedError, ToolCall, ToolSpec,
    normalize_messages, parse_structured,
)

log = logging.getLogger(__name__)


class LLMClientProtocol(Protocol):
    def generate(self, model: str, messages: list[dict], system: Optional[str] = None,
                 tools: Optional[list[ToolSpec]] = None, temperature: float = 0.0,
                 json_mode: bool = False, response_schema: Optional[type] = None,
                 use_cache: bool = True, cache_salt: Optional[str] = None) -> LLMResponse: ...


def _to_contents(messages: list[dict]) -> list[gt.Content]:
    """Messages with `raw` pass through untouched; the rest are built from dicts."""
    contents = []
    for m in messages:
        if m.get("raw") is not None:
            contents.append(m["raw"])
        elif m["role"] == "tool":
            parts = [gt.Part.from_function_response(name=r["name"], response=r["response"])
                     for r in m["results"]]
            contents.append(gt.Content(role="user", parts=parts))
        else:
            parts = [gt.Part(text=m["text"])] if m.get("text") else []
            for c in m.get("tool_calls", []):
                call = c if isinstance(c, dict) else {"name": c.name, "args": c.args}
                parts.append(gt.Part.from_function_call(name=call["name"], args=call["args"]))
            contents.append(gt.Content(role=m["role"], parts=parts))
    return contents


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, rpm_limit: int = 10,
                 timeout_s: int = 60, cache: Optional[DiskCache] = None,
                 genai_client: Any = None, max_attempts: int = 5,
                 sleep: Callable[[float], None] = time.sleep,
                 limiter: Optional[RateLimiter] = None):
        self._api_key, self._timeout_s = api_key, timeout_s
        self._genai = genai_client
        self.cache = cache or DiskCache()
        self.max_attempts, self._sleep = max_attempts, sleep
        self.limiter = limiter or RateLimiter(rpm_limit, sleep=sleep)

    @classmethod
    def from_config(cls, cfg: Config) -> "LLMClient":
        return cls(api_key=cfg.gemini_api_key, rpm_limit=cfg.rpm_limit,
                   timeout_s=cfg.request_timeout_s)

    def generate(self, model: str, messages: list[dict], system: Optional[str] = None,
                 tools: Optional[list[ToolSpec]] = None, temperature: float = 0.0,
                 json_mode: bool = False, response_schema: Optional[type] = None,
                 use_cache: bool = True, cache_salt: Optional[str] = None) -> LLMResponse:
        if response_schema and tools:
            raise ValueError("response_schema cannot be combined with tools")
        key = make_key({
            "model": model, "messages": normalize_messages(messages), "system": system,
            "tools": [vars(t) for t in tools or []], "temperature": temperature,
            "json_mode": json_mode, "salt": cache_salt,
            "schema": response_schema.model_json_schema() if response_schema else None,
        })
        if use_cache and (entry := self.cache.get(key)):
            resp = LLMResponse.from_entry(entry)
            if response_schema:
                resp.parsed = parse_structured(resp.text, response_schema)
            return resp  # original latency/tokens, cached=True

        config = self._build_config(system, tools, temperature, json_mode, response_schema)
        resp = self._with_retries(model, _to_contents(messages), config)
        if response_schema:
            if not resp.cacheable:
                raise LLMResponseError(
                    f"No usable structured reply (finish_reason={resp.finish_reason})")
            resp.parsed = parse_structured(resp.text, response_schema)  # raises, uncached
        if use_cache and resp.cacheable:
            self.cache.put(key, resp.to_entry())
        log.info("llm model=%s latency_ms=%d in=%d out=%d", model, resp.latency_ms,
                 resp.input_tokens, resp.output_tokens)
        return resp

    def _build_config(self, system, tools, temperature, json_mode, schema):
        kwargs: dict = {"system_instruction": system, "temperature": temperature}
        if tools:
            decls = [gt.FunctionDeclaration(name=t.name, description=t.description,
                                            parameters_json_schema=t.parameters) for t in tools]
            kwargs["tools"] = [gt.Tool(function_declarations=decls)]
            kwargs["automatic_function_calling"] = gt.AutomaticFunctionCallingConfig(disable=True)
        if schema:
            kwargs.update(response_mime_type="application/json", response_schema=schema)
        elif json_mode:
            kwargs["response_mime_type"] = "application/json"
        return gt.GenerateContentConfig(**kwargs)

    def _with_retries(self, model, contents, config) -> LLMResponse:
        for attempt in range(self.max_attempts):
            self.limiter.wait()
            try:
                return self._call_api(model, contents, config)
            except Exception as exc:
                if is_daily_quota(exc):
                    raise QuotaExhaustedError(
                        f"Daily quota exhausted for model '{model}'. Retrying will not help: "
                        "wait for the reset, use another model, or use another key."
                    ) from exc
                if not is_retryable(exc) or attempt == self.max_attempts - 1:
                    raise
                delay = backoff_delay(attempt, exc)
                log.warning("llm retry %d after %s, sleeping %.1fs",
                            attempt + 1, type(exc).__name__, delay)
                self._sleep(delay)
        raise AssertionError("unreachable")

    def _http_options(self) -> gt.HttpOptions:
        """attempts=1 turns off the SDK's own retries: only _with_retries retries, so every
        attempt passes the rate limiter and the daily-quota check."""
        return gt.HttpOptions(timeout=self._timeout_s * 1000,  # milliseconds, per attempt
                              retry_options=gt.HttpRetryOptions(attempts=1))

    def _call_api(self, model, contents, config) -> LLMResponse:
        if self._genai is None:
            self._genai = genai.Client(api_key=self._api_key, http_options=self._http_options())
        start = time.perf_counter()
        raw = self._genai.models.generate_content(model=model, contents=contents, config=config)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return self._parse(raw, latency_ms)

    @staticmethod
    def _parse(raw, latency_ms: int) -> LLMResponse:
        usage = raw.usage_metadata
        resp = LLMResponse(
            latency_ms=latency_ms,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            # thinking tokens are billed as output, so count them
            output_tokens=((usage.candidates_token_count or 0)
                           + (usage.thoughts_token_count or 0)) if usage else 0,
        )
        if not raw.candidates:  # prompt blocked before generation
            resp.finish_reason = "BLOCKED"
            return resp
        cand = raw.candidates[0]
        resp.finish_reason = cand.finish_reason.name if cand.finish_reason else "STOP"
        resp.raw_content = cand.content
        for part in (cand.content.parts if cand.content and cand.content.parts else []):
            if part.function_call:
                resp.tool_calls.append(
                    ToolCall(part.function_call.name, dict(part.function_call.args or {})))
            elif part.text and not part.thought:
                resp.text += part.text
        return resp
