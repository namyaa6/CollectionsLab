from backend.eval.retrieval_stats import retrieval_stats
from backend.tests.eval_helpers import make_transcript


def search(query, results):
    return {"tool": "search_policy", "args": {"query": query}, "result": {"results": results}}


def test_counts_calls_empty_results_and_queries():
    t = make_transcript([
        ("agent", "Hi.", [search("installment rules", [{"section": "a", "text": "b"}])]),
        ("debtor", "Hello."),
        ("agent", "Ok.", [search("zzz", []), {"tool": "get_invoice", "args": {}, "result": {}}]),
    ])
    s = retrieval_stats(t)
    assert (s.search_calls, s.empty_results, s.queries) == (2, 1, ["installment rules", "zzz"])


def test_error_result_counts_as_empty():
    t = make_transcript([("agent", "Hi.", [
        {"tool": "search_policy", "args": {"query": "x"}, "result": {"error": "bad"}}])])
    assert retrieval_stats(t).empty_results == 1


def test_no_searches():
    s = retrieval_stats(make_transcript([("agent", "Hi.")]))
    assert (s.search_calls, s.empty_results, s.queries) == (0, 0, [])
