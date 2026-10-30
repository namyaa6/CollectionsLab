import httpx
import pytest

from backend.llm.retry import RateLimiter, backoff_delay
from backend.llm.types import QuotaExhaustedError
from backend.tests.llm_helpers import MSGS, api_error, make_client, make_response


@pytest.mark.parametrize("code", [429, 500, 503, 504])
def test_retries_then_succeeds(tmp_path, code):
    client, stub, sleeps = make_client(tmp_path, [api_error(code), make_response("ok")])
    assert client.generate("m", MSGS).text == "ok"
    assert len(stub.calls) == 2 and len(sleeps) == 1


def test_retries_network_timeout(tmp_path):
    client, stub, _ = make_client(tmp_path, [httpx.ReadTimeout("slow"), make_response("ok")])
    assert client.generate("m", MSGS).text == "ok"
    assert len(stub.calls) == 2


def test_backoff_grows(tmp_path):
    errs = [api_error(503), api_error(503), api_error(503), make_response("ok")]
    client, _, sleeps = make_client(tmp_path, errs)
    client.generate("m", MSGS)
    assert len(sleeps) == 3
    assert sleeps[0] < sleeps[1] < sleeps[2]  # 2+j, 4+j, 8+j with j in [0, 1)


def test_server_retry_delay_is_used(tmp_path):
    client, _, sleeps = make_client(
        tmp_path, [api_error(429, retry_delay="7s"), make_response("ok")])
    client.generate("m", MSGS)
    assert sleeps == [7.0]


def test_retry_delay_from_message(tmp_path):
    err = api_error(429, message="Please retry in 3.5s.")
    assert backoff_delay(0, err) == 3.5


def test_gives_up_after_max_attempts(tmp_path):
    client, stub, sleeps = make_client(tmp_path, [api_error(503)] * 3, max_attempts=3)
    with pytest.raises(Exception) as err:
        client.generate("m", MSGS)
    assert err.value.code == 503
    assert len(stub.calls) == 3 and len(sleeps) == 2


def test_non_retryable_raises_immediately(tmp_path):
    client, stub, sleeps = make_client(tmp_path, [api_error(400), make_response("never")])
    with pytest.raises(Exception) as err:
        client.generate("m", MSGS)
    assert err.value.code == 400
    assert len(stub.calls) == 1 and sleeps == []


@pytest.mark.parametrize("err", [
    api_error(429, violations=["GenerateRequestsPerDayPerProjectPerModel-FreeTier"]),
    api_error(429, message="You exceeded your daily quota"),
])
def test_daily_quota_stops_immediately(tmp_path, err):
    client, stub, sleeps = make_client(tmp_path, [err, make_response("never")])
    with pytest.raises(QuotaExhaustedError, match="Daily quota"):
        client.generate("my-model", MSGS)
    assert len(stub.calls) == 1 and sleeps == []


def test_per_minute_429_is_retried(tmp_path):
    err = api_error(429, violations=["GenerateRequestsPerMinutePerProjectPerModel"])
    client, stub, _ = make_client(tmp_path, [err, make_response("ok")])
    assert client.generate("m", MSGS).text == "ok"
    assert len(stub.calls) == 2


def test_rate_limiter_delays_extra_call():
    now, sleeps = [0.0], []

    def fake_sleep(s):
        sleeps.append(s)
        now[0] += s

    limiter = RateLimiter(2, clock=lambda: now[0], sleep=fake_sleep)
    limiter.wait()
    now[0] = 1
    limiter.wait()
    now[0] = 2
    limiter.wait()  # third call within 60s must wait until the first expires
    assert sleeps == [58.0]
