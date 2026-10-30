import pytest
from google.genai import types as gt
from pydantic import BaseModel

from backend.llm.types import LLMResponseError, ToolSpec
from backend.tests.llm_helpers import MSGS, make_client, make_response


class Verdict(BaseModel):
    ok: bool
    score: int


def test_response_schema_returns_parsed_object(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response('{"ok": true, "score": 4}')])
    resp = client.generate("m", MSGS, response_schema=Verdict)
    assert resp.parsed == Verdict(ok=True, score=4)
    config = stub.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is Verdict


def test_cache_hit_still_returns_parsed(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response('{"ok": false, "score": 1}')])
    client.generate("m", MSGS, response_schema=Verdict)
    hit = client.generate("m", MSGS, response_schema=Verdict)
    assert hit.cached and hit.parsed == Verdict(ok=False, score=1)
    assert len(stub.calls) == 1


def test_invalid_json_raises_and_is_not_cached(tmp_path):
    client, _, _ = make_client(tmp_path, [make_response('{"ok": "maybe"}')])
    with pytest.raises(LLMResponseError, match="Verdict"):
        client.generate("m", MSGS, response_schema=Verdict)
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.parametrize("resp, reason", [
    (make_response(""), "STOP"),
    (make_response('{"ok": true, "score": 1}', finish="MAX_TOKENS"), "MAX_TOKENS"),
    (make_response("x", finish="SAFETY"), "SAFETY"),
    (gt.GenerateContentResponse(candidates=[]), "BLOCKED"),
])
def test_uncacheable_reply_with_schema_raises_naming_finish_reason(tmp_path, resp, reason):
    client, _, _ = make_client(tmp_path, [resp])
    with pytest.raises(LLMResponseError, match=f"finish_reason={reason}"):
        client.generate("m", MSGS, response_schema=Verdict)
    assert list(tmp_path.glob("*.json")) == []


def test_schema_and_tools_rejected(tmp_path):
    client, _, _ = make_client(tmp_path, [])
    with pytest.raises(ValueError):
        client.generate("m", MSGS, response_schema=Verdict,
                        tools=[ToolSpec("f", "d", {"type": "object"})])


def test_json_mode_returns_plain_text(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response('{"a": 1}')])
    resp = client.generate("m", MSGS, json_mode=True)
    assert resp.text == '{"a": 1}' and resp.parsed is None
    assert stub.calls[0]["config"].response_mime_type == "application/json"
    assert stub.calls[0]["config"].response_schema is None
