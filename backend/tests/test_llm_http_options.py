import httpx
from google import genai

from backend.llm.client import LLMClient


def test_sdk_retries_disabled_in_http_options():
    opts = LLMClient(api_key="x", timeout_s=30)._http_options()
    assert opts.retry_options.attempts == 1
    assert opts.timeout == 30_000


def test_real_sdk_client_makes_one_request_on_503():
    hits = []

    def handler(request):
        hits.append(request)
        body = {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}}
        return httpx.Response(503, json=body)

    opts = LLMClient(api_key="x")._http_options()
    transport = httpx.MockTransport(handler)
    opts = opts.model_copy(update={"httpx_client": httpx.Client(transport=transport)})
    sdk = genai.Client(api_key="x", http_options=opts)
    try:
        sdk.models.generate_content(model="m", contents="hi")
    except Exception:
        pass
    assert len(hits) == 1
