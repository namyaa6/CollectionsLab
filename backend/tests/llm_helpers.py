"""Stub genai client and response builders shared by the LLM tests."""
from google.genai import errors
from google.genai import types as gt

from backend.llm.cache import DiskCache
from backend.llm.client import LLMClient


def make_response(text="hello", finish="STOP", parts=None, tokens_in=3, tokens_out=4):
    parts = parts if parts is not None else [gt.Part(text=text)]
    cand = gt.Candidate(content=gt.Content(role="model", parts=parts),
                        finish_reason=gt.FinishReason(finish))
    return gt.GenerateContentResponse(
        candidates=[cand],
        usage_metadata=gt.GenerateContentResponseUsageMetadata(
            prompt_token_count=tokens_in, candidates_token_count=tokens_out))


def api_error(code, message="boom", violations=None, retry_delay=None):
    details = []
    if violations:
        details.append({"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": v} for v in violations]})
    if retry_delay:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": retry_delay})
    body = {"error": {"code": code, "message": message, "status": "X", "details": details}}
    return errors.APIError(code, body)


class StubGenai:
    """Stands in for genai.Client: .models.generate_content pops scripted items."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(tmp_path, script, **kwargs):
    stub = StubGenai(script)
    sleeps = []
    client = LLMClient(cache=DiskCache(tmp_path), genai_client=stub, rpm_limit=1000,
                       sleep=sleeps.append, **kwargs)
    return client, stub, sleeps


MSGS = [{"role": "user", "text": "hi"}]
