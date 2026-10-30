import pytest
from pydantic import BaseModel

from backend.llm import list_models
from backend.llm.fake import FakeLLMClient, text_reply, tool_reply


class Out(BaseModel):
    n: int


def test_script_order_and_recording():
    fake = FakeLLMClient([text_reply("one"), tool_reply("end_call", {"reason": "x"})])
    assert fake.generate("m", [{"role": "user", "text": "a"}], system="s").text == "one"
    second = fake.generate("m", [])
    assert second.tool_calls[0].name == "end_call"
    assert len(fake.calls) == 2 and fake.calls[0]["system"] == "s"


def test_callable_entries_see_the_request():
    fake = FakeLLMClient([lambda req: text_reply(req["messages"][0]["text"].upper())])
    assert fake.generate("m", [{"role": "user", "text": "hey"}]).text == "HEY"


def test_exhausted_script_is_a_clear_error():
    with pytest.raises(AssertionError, match="exhausted"):
        FakeLLMClient([]).generate("m", [])


def test_response_schema_is_parsed():
    fake = FakeLLMClient([text_reply('{"n": 3}')])
    assert fake.generate("m", [], response_schema=Out).parsed == Out(n=3)


class _Model:
    def __init__(self, name, actions):
        self.name, self.supported_actions = name, actions


class _Stub:
    def __init__(self, models):
        self.models = self
        self._models = models

    def list(self):
        return self._models


def test_list_generate_models_filters_and_strips_prefix():
    stub = _Stub([_Model("models/b-chat", ["generateContent"]),
                  _Model("models/embed", ["embedContent"]),
                  _Model("models/a-chat", ["generateContent", "countTokens"]),
                  _Model("models/none", None)])
    assert list_models.list_generate_models(stub) == ["a-chat", "b-chat"]


def test_list_models_main_never_prints_key(monkeypatch, capsys):
    monkeypatch.setattr(list_models, "get_api_key", lambda: "super-secret")

    class Boom:
        def __init__(self, api_key):
            raise RuntimeError(f"bad key {api_key}")

    monkeypatch.setattr(list_models.genai, "Client", Boom)
    assert list_models.main() == 1
    assert "super-secret" not in capsys.readouterr().out
