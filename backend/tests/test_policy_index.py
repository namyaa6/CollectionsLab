import math

import pytest

from backend.rag.policy_index import MIN_RELATIVE_SCORE, PolicyIndex, load_chunks, tokenize

TITLES = [
    "Identity Verification", "Calling Etiquette", "Installment Rules",
    "Payment Promise Window", "No Discounts or Waivers", "No Threats or Legal Claims",
    "Dispute Handling", "Payment Claim Handling", "Escalation Triggers", "Language",
]


@pytest.fixture(scope="module")
def index():
    return PolicyIndex.from_file()


def test_chunks_are_the_ten_sections():
    assert [c.title for c in load_chunks()] == TITLES
    assert all(c.text for c in load_chunks())


@pytest.mark.parametrize("query,expected", [
    ("can I split the payment into installments", "Installment Rules"),
    ("customer says GST amount is wrong", "Dispute Handling"),
    ("I already paid, what UTR do I ask for", "Payment Claim Handling"),
    ("can I give a discount or waive the late fee", "No Discounts or Waivers"),
    ("customer wants to pay in 45 days", "Payment Promise Window"),
])
def test_top_result_is_the_right_section(index, query, expected):
    assert index.search(query)[0]["section"] == expected


# Held-out queries: written after the BM25 settings were fixed and never used to tune them.
# Known limitation: BM25 matches words, not meaning. It misses paraphrases that share no word
# with the policy text, and stemming is only plural-stripping. Cases marked xfail fail today;
# strict=True means the suite flags it if retrieval ever starts getting them right.
HELD_OUT = [
    # (query, expected section, passes at top-1, passes at top-3)
    # "bill"/"extra"/"item" are not in the Dispute section; "item" only hits other sections.
    ("they say the bill has an extra item", "Dispute Handling", False, False),
    # no word overlap with the policy ("knock", "off", "total"), so nothing is returned.
    ("can we knock something off the total", "No Discounts or Waivers", False, False),
    # "swearing" is not in the policy (it says "insults"/"abusive"), so nothing is returned.
    ("the customer is swearing at me", "Escalation Triggers", False, False),
    ("speak in Hindi?", "Language", True, True),
    # "NEFT" is not in the policy; "payment"/"week" favour Installment Rules at rank 1.
    ("payment was made via NEFT last week", "Payment Claim Handling", False, True),
]


def _held_out_params():
    for query, expected, top1, top3 in HELD_OUT:
        for k, passes in ((1, top1), (3, top3)):
            marks = [] if passes else [pytest.mark.xfail(
                strict=True, reason=f"known limitation: {expected!r} not in top-{k}")]
            yield pytest.param(query, expected, k, marks=marks, id=f"top{k}-{query[:30]}")


@pytest.mark.parametrize("query,expected,k", list(_held_out_params()))
def test_held_out_queries(index, query, expected, k):
    assert expected in [r["section"] for r in index.search(query, k=k)]


def test_legal_threat_query_returns_escalation_in_top_two(index):
    # "No Threats or Legal Claims" legitimately shares "threaten" and "lawyer", so it can
    # rank first; the agent gets both sections and Escalation Triggers must be one of them.
    sections = [r["section"] for r in index.search("debtor threatens to call a lawyer")]
    assert "Escalation Triggers" in sections[:2]


def test_k_is_respected_and_scores_are_positive_and_sorted(index):
    results = index.search("payment amount call", k=2)
    assert len(results) <= 2
    scores = [r["score"] for r in results]
    assert all(s > 0 for s in scores) and scores == sorted(scores, reverse=True)


def test_no_overlap_query_returns_nothing(index):
    assert index.search("what is the weather in Mumbai") == []
    assert index.search("") == []


def test_weak_tail_hits_are_filtered_relative_to_the_best(index):
    results = index.search("customer says GST amount is wrong", k=10)
    top = results[0]["score"]
    assert all(r["score"] >= top * MIN_RELATIVE_SCORE for r in results)
    # without the filter, more chunks share a term with this query
    assert sum(s > 0 for s in index.scores("customer says GST amount is wrong")) > len(results)


def test_idf_is_positive_even_for_terms_in_most_chunks(index):
    assert all(v > 0 for v in index.idf.values())
    n = len(index.chunks)
    okapi_idf = math.log((n - 8 + 0.5) / (8 + 0.5))  # a term in 8 of 10 chunks, e.g. "debtor"
    assert okapi_idf < 0 < index.idf["debtor"]


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("The installments are due") == ["installment", "due"]
