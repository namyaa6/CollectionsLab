"""How the agent used search_policy in one call."""
from backend.eval.models import RetrievalStats
from backend.sim.transcript import Transcript


def retrieval_stats(t: Transcript) -> RetrievalStats:
    stats = RetrievalStats()
    for turn in t.turns:
        for call in turn.tool_calls:
            if call.get("tool") != "search_policy":
                continue
            stats.search_calls += 1
            stats.queries.append(str(call.get("args", {}).get("query", "")))
            result = call.get("result") or {}
            if "error" in result or not result.get("results"):
                stats.empty_results += 1
    return stats
