import pytest

from backend import config
from backend.config import ConfigError, get_api_key, get_config

ALL = {"GEMINI_API_KEY": "secret-key-123", "AGENT_MODEL": "a", "SIM_MODEL": "s",
       "JUDGE_MODEL": "j", "RPM_LIMIT": "10"}


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)  # never read real .env
    for name in [*ALL, "LLM_TIMEOUT_S"]:
        monkeypatch.delenv(name, raising=False)


def set_env(monkeypatch, **overrides):
    for name, value in {**ALL, **overrides}.items():
        monkeypatch.setenv(name, value)


def test_loads_all_values(monkeypatch):
    set_env(monkeypatch)
    cfg = get_config()
    assert (cfg.agent_model, cfg.sim_model, cfg.judge_model) == ("a", "s", "j")
    assert cfg.rpm_limit == 10
    assert cfg.request_timeout_s == 60


def test_timeout_override(monkeypatch):
    set_env(monkeypatch, LLM_TIMEOUT_S="15")
    assert get_config().request_timeout_s == 15


@pytest.mark.parametrize("name", list(ALL))
def test_missing_variable_is_named(monkeypatch, name):
    set_env(monkeypatch, **{name: ""})
    with pytest.raises(ConfigError) as err:
        get_config()
    assert name in str(err.value)
    assert "secret-key-123" not in str(err.value)


@pytest.mark.parametrize("bad", ["abc", "0", "-3"])
def test_bad_rpm(monkeypatch, bad):
    set_env(monkeypatch, RPM_LIMIT=bad)
    with pytest.raises(ConfigError, match="RPM_LIMIT"):
        get_config()


def test_key_never_in_repr(monkeypatch):
    set_env(monkeypatch)
    assert "secret-key-123" not in repr(get_config())


def test_api_key_alone_does_not_need_models(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert get_api_key() == "k"


def test_api_key_missing(monkeypatch):
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        get_api_key()
