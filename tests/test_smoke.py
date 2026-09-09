"""Week 1 checks: a request goes in, a reply comes out, nothing costs money.

These run with no key, no network and no models, so `pytest` on a fresh clone
just works. That rule holds for every test file we add later.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings, get_settings
from app.providers import SpendCapExceeded, SpendLedger, cost_usd
from app.schemas import ChatMessage, prompt_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "mock")
    monkeypatch.setenv("SCREENING_SCORER", "stub")
    monkeypatch.setenv("CACHE_EMBEDDER", "stub")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("SENTRYGATE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def ask(client, prompt="what is the capital of France?", **extra):
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
    body.update(extra)
    return client.post("/v1/chat/completions", json=body)


def test_healthz_reports_the_running_config(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["provider_mode"] == "mock"
    assert body["config"]["verdict_filter"] == "off"
    assert body["config"]["pipeline_order"] == "cache_first"


def test_a_request_gets_an_openai_shaped_reply(client):
    response = ask(client)
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] > 0


def test_headers_say_screened_and_cache_miss_on_first_ask(client):
    headers = ask(client).headers
    assert headers["X-SentryGate-Screened"] == "true"
    assert headers["X-SentryGate-Verdict"] == "clean"
    assert headers["X-SentryGate-Cache"] == "miss"
    assert headers["X-SentryGate-Provider"] == "mock"
    assert len(headers["X-SentryGate-Request-Id"]) == 32


def test_streaming_is_refused_clearly(client):
    response = ask(client, stream=True)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "stream_not_supported"


def test_an_empty_request_is_refused(client):
    response = client.post("/v1/chat/completions", json={"model": "x", "messages": []})
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_replay_without_a_recording_says_so(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    monkeypatch.setenv("SCREENING_SCORER", "stub")
    monkeypatch.setenv("CACHE_EMBEDDER", "stub")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("SENTRYGATE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        response = ask(test_client)
    get_settings.cache_clear()
    assert response.status_code == 503
    assert response.json()["error"]["type"] == "cassette_missing"


def test_replay_serves_a_recording(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    monkeypatch.setenv("SCREENING_SCORER", "stub")
    monkeypatch.setenv("CACHE_EMBEDDER", "stub")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("SENTRYGATE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    prompt = "what is the capital of France?"
    key = prompt_hash("gpt-4o-mini", [ChatMessage(role="user", content=prompt)])
    cassettes = tmp_path / "cassettes"
    cassettes.mkdir(parents=True)
    (cassettes / f"{key}.json").write_text(json.dumps({
        "model": "gpt-4o-mini", "text": "Paris.", "tokens_in": 8, "tokens_out": 2,
    }))
    from app.main import app

    with TestClient(app) as test_client:
        response = ask(test_client, prompt=prompt)
    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Paris."
    assert response.headers["X-SentryGate-Provider"] == "replay"


def test_live_without_a_key_fails_at_startup(monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ConfigError):
        Settings.from_env()
    get_settings.cache_clear()


def test_spend_cap_refuses_before_the_call(tmp_path):
    ledger = SpendLedger(tmp_path / "ledger.json", cap_usd=0.10)
    ledger.record(0.09)
    assert ledger.spent_today() == pytest.approx(0.09)
    with pytest.raises(SpendCapExceeded):
        ledger.check(0.05)
    ledger.check(0.005)  # under the cap, so it is allowed


def test_cost_maths_matches_the_price_table():
    # 1M input tokens of gpt-4o-mini is $0.15, 1M output is $0.60.
    assert cost_usd("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert cost_usd("gpt-4o-mini", 0, 1_000_000) == pytest.approx(0.60)
