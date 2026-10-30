from google.genai import types as gt

from backend.llm.types import ToolSpec
from backend.tests.llm_helpers import MSGS, make_client, make_response


def test_text_response_parsed(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response("hi there", tokens_in=7, tokens_out=9)])
    resp = client.generate("m1", MSGS, system="be brief")
    assert (resp.text, resp.input_tokens, resp.output_tokens) == ("hi there", 7, 9)
    assert resp.latency_ms >= 0 and resp.cached is False
    assert stub.calls[0]["model"] == "m1"
    assert stub.calls[0]["config"].system_instruction == "be brief"


def test_function_call_parsed_and_declared(tmp_path):
    part = gt.Part.from_function_call(name="get_invoice", args={"invoice_id": "INV-1"})
    client, stub, _ = make_client(tmp_path, [make_response(parts=[part])])
    tool = ToolSpec("get_invoice", "Look up an invoice",
                    {"type": "object", "properties": {"invoice_id": {"type": "string"}}})
    resp = client.generate("m", MSGS, tools=[tool])
    assert resp.tool_calls[0].name == "get_invoice"
    assert resp.tool_calls[0].args == {"invoice_id": "INV-1"}
    decl = stub.calls[0]["config"].tools[0].function_declarations[0]
    assert decl.name == "get_invoice"


def test_thinking_parts_excluded_from_text(tmp_path):
    parts = [gt.Part(text="private thoughts", thought=True), gt.Part(text="answer")]
    client, _, _ = make_client(tmp_path, [make_response(parts=parts)])
    assert client.generate("m", MSGS).text == "answer"


def test_raw_content_replayed_unchanged(tmp_path):
    part = gt.Part(function_call=gt.FunctionCall(name="end_call", args={}),
                   thought_signature=b"\x01\x02sig")
    client, stub, _ = make_client(tmp_path, [make_response(parts=[part]), make_response("ok")])
    first = client.generate("m", MSGS)
    history = MSGS + [
        {"role": "model", "raw": first.raw_content},
        {"role": "tool", "results": [{"name": "end_call", "response": {"ok": True}}]},
    ]
    client.generate("m", history)
    sent = stub.calls[1]["contents"]
    assert sent[1] is first.raw_content  # same object, not rebuilt
    assert sent[1].parts[0].thought_signature == b"\x01\x02sig"
    assert sent[2].parts[0].function_response.name == "end_call"


def test_dict_messages_with_tool_calls_are_built(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response("ok")])
    history = [{"role": "user", "text": "x"},
               {"role": "model", "text": "calling", "tool_calls": [{"name": "f", "args": {"a": 1}}]}]
    client.generate("m", history)
    model_turn = stub.calls[0]["contents"][1]
    assert model_turn.role == "model"
    assert model_turn.parts[1].function_call.name == "f"
