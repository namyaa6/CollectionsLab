import pytest
from google.genai import types as gt

from backend.llm import cache as cache_cli
from backend.llm.cache import DiskCache
from backend.tests.llm_helpers import MSGS, make_client, make_response


def test_hit_skips_api_and_keeps_original_latency_and_tokens(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response("one", tokens_in=11, tokens_out=22)])
    first = client.generate("m", MSGS)
    second = client.generate("m", MSGS)  # script is empty: an API call would raise
    assert len(stub.calls) == 1
    assert second.cached is True and first.cached is False
    assert (second.text, second.input_tokens, second.output_tokens) == ("one", 11, 22)
    assert second.latency_ms == first.latency_ms


def test_different_params_do_not_collide(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response("a"), make_response("b"),
                                             make_response("c"), make_response("d")])
    client.generate("m", MSGS)
    client.generate("m", MSGS, temperature=0.7)
    client.generate("m2", MSGS)
    client.generate("m", MSGS, cache_salt="seed-2")
    assert len(stub.calls) == 4


@pytest.mark.parametrize("resp", [
    make_response(""),
    make_response("cut off", finish="MAX_TOKENS"),
    make_response("blocked", finish="SAFETY"),
    gt.GenerateContentResponse(candidates=[]),
])
def test_bad_responses_are_not_cached(tmp_path, resp):
    client, stub, _ = make_client(tmp_path, [resp, make_response("good")])
    client.generate("m", MSGS)
    assert DiskCache(tmp_path).count() == 0
    assert client.generate("m", MSGS).text == "good"  # went to the API again
    assert len(stub.calls) == 2


def test_exceptions_are_not_cached(tmp_path):
    client, _, _ = make_client(tmp_path, [ValueError("bad")])
    with pytest.raises(ValueError):
        client.generate("m", MSGS)
    assert DiskCache(tmp_path).count() == 0


def test_use_cache_false_neither_reads_nor_writes(tmp_path):
    client, stub, _ = make_client(
        tmp_path, [make_response("a"), make_response("b"), make_response("c")])
    client.generate("m", MSGS, use_cache=False)
    assert DiskCache(tmp_path).count() == 0
    client.generate("m", MSGS)  # populates
    again = client.generate("m", MSGS, use_cache=False)  # ignores the entry
    assert again.text == "c" and again.cached is False
    assert len(stub.calls) == 3


def test_corrupt_file_is_a_miss(tmp_path):
    client, stub, _ = make_client(tmp_path, [make_response("a"), make_response("b")])
    client.generate("m", MSGS)
    for f in tmp_path.glob("*.json"):
        f.write_text("{not json", encoding="utf-8")
    assert client.generate("m", MSGS).text == "b"


def test_raw_content_survives_cache_round_trip(tmp_path):
    part = gt.Part(function_call=gt.FunctionCall(name="end_call", args={"reason": "done"}),
                   thought_signature=b"\x00\xffsignature")
    client, _, _ = make_client(tmp_path, [make_response(parts=[part])])
    client.generate("m", MSGS)
    hit = client.generate("m", MSGS)
    assert hit.cached and hit.tool_calls[0].args == {"reason": "done"}
    assert hit.raw_content.parts[0].thought_signature == b"\x00\xffsignature"


def test_cli_clear_and_stats(tmp_path, capsys):
    cache = DiskCache(tmp_path)
    cache.put("k1", {"a": 1})
    cache.put("k2", {"a": 2})
    cache_cli.main(["--stats"], cache=cache)
    assert "2 cached" in capsys.readouterr().out
    cache_cli.main(["--clear"], cache=cache)
    assert "Deleted 2" in capsys.readouterr().out
    assert cache.count() == 0
