"""The request log is the data source for every later number, so it gets tests.

What matters here is not that logging works. It is that a line is always
written, always complete, and never contains the prompt itself.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.logging_mw import client_key_id


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "mock")
    monkeypatch.setenv("SENTRYGATE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        yield client, tmp_path / "requests.jsonl"
    get_settings.cache_clear()


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def ask(client, prompt="what is the capital of France?", **extra):
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
    body.update(extra)
    return client.post("/v1/chat/completions", json=body)


def test_one_request_writes_one_complete_line(gateway):
    client, log_path = gateway
    ask(client)
    lines = read_lines(log_path)
    assert len(lines) == 1
    line = lines[0]
    for key in ("ts", "request_id", "api_key_id", "prompt_hash", "prompt_len",
                "screening_ran", "cache", "tokens", "cost_usd", "latency_ms",
                "status", "config"):
        assert key in line, f"missing {key}"
    assert line["status"] == 200
    assert line["tokens"]["in"] > 0
    assert line["latency_ms"]["total"] > 0
    assert line["latency_ms"]["provider"] >= 0


def test_the_prompt_itself_is_never_logged(gateway):
    client, log_path = gateway
    secret = "my password is hunter2 and my email is a@b.com"
    ask(client, prompt=secret)
    raw = log_path.read_text()
    assert "hunter2" not in raw
    assert "a@b.com" not in raw
    assert read_lines(log_path)[0]["prompt_len"] == len(secret)


def test_the_line_says_nothing_was_screened_or_cached_yet(gateway):
    client, log_path = gateway
    ask(client)
    line = read_lines(log_path)[0]
    assert line["screening_ran"] is False
    assert line["verdict"] is None
    assert line["cache"]["outcome"] == "disabled"


def test_every_line_carries_the_settings_that_produced_it(gateway):
    client, log_path = gateway
    ask(client)
    config = read_lines(log_path)[0]["config"]
    assert config["pipeline_order"] == "cache_first"
    assert config["verdict_filter"] == "off"
    assert config["provider_mode"] == "mock"
    assert config["build_sha"]


def test_a_refused_request_is_logged_with_its_reason(gateway):
    client, log_path = gateway
    response = ask(client, stream=True)
    assert response.status_code == 400
    line = read_lines(log_path)[0]
    assert line["status"] == 400
    assert line["block_reason"] == "invalid_request_error"


def test_health_checks_do_not_pollute_the_log(gateway):
    client, log_path = gateway
    client.get("/healthz")
    client.get("/healthz")
    assert not log_path.exists() or read_lines(log_path) == []


def test_the_request_id_comes_back_on_the_response(gateway):
    client, _ = gateway
    headers = ask(client).headers
    assert len(headers["X-SentryGate-Request-Id"]) == 32


def test_a_caller_key_is_hashed_not_stored():
    assert client_key_id(None) == "anonymous"
    hashed = client_key_id("Bearer sk-secret-value")
    assert hashed.startswith("sha256:")
    assert "secret" not in hashed
