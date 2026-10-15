"""Phase 3 checks: the difficulty router and the fallback model."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.providers import MockProvider, UpstreamError
from app.router import difficulty, route

EASY = "what is the capital of France?"
HARD = "Write a Python function to merge two sorted lists, and explain its time complexity step by step."


def settings(**over) -> Settings:
    get_settings.cache_clear()
    base = Settings.from_env()
    return base.__class__(**{**base.__dict__, **over})


@pytest.fixture(autouse=True)
def _reset():
    yield
    get_settings.cache_clear()


def test_easy_and_hard_questions_score_apart():
    easy, _ = difficulty(EASY)
    hard, reasons = difficulty(HARD)
    assert easy == 0.0
    assert hard >= 0.4 and "code" in reasons


def test_fixed_mode_keeps_the_requested_model():
    s = settings(router_mode="fixed")
    assert route(s, "gpt-4o-mini", HARD).model == "gpt-4o-mini"
    assert route(s, None, HARD).model == s.default_model


def test_difficulty_mode_picks_cheap_or_strong():
    s = settings(router_mode="difficulty", router_cheap_model="cheap-m", router_strong_model="strong-m",
                 router_hard_score=0.4)
    assert route(s, "gpt-4o-mini", EASY).tier == "cheap"
    decision = route(s, "gpt-4o-mini", HARD)
    assert decision.tier == "strong" and decision.model == "strong-m"


class FlakyProvider(MockProvider):
    """Fails for one model, answers for the rest."""

    def __init__(self, broken: str):
        self.broken = broken

    def complete(self, request, model):
        if model == self.broken:
            raise UpstreamError(f"{model} is down")
        return super().complete(request, model)


def gateway(tmp_path, monkeypatch, **env):
    base = {"PROVIDER_MODE": "mock", "SCREENING_SCORER": "stub", "CACHE_EMBEDDER": "stub",
            "CACHE_BACKEND": "memory", "SENTRYGATE_DATA_DIR": str(tmp_path)}
    for k, v in {**base, **env}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def ask(client, prompt):
    return client.post("/v1/chat/completions",
                       json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]})


def last_line(tmp_path):
    return json.loads((tmp_path / "requests.jsonl").read_text().splitlines()[-1])


def test_router_sends_a_hard_question_to_the_strong_model(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, ROUTER_MODE="difficulty", ROUTER_STRONG_MODEL="gpt-4o") as c:
        r = ask(c, HARD)
        assert r.status_code == 200 and r.headers["X-SentryGate-Route"] == "strong"
        line = last_line(tmp_path)
        assert line["model_used"] == "gpt-4o" and line["route"]["tier"] == "strong"
        r = ask(c, EASY)
        assert r.headers["X-SentryGate-Route"] == "cheap"


def test_failover_answers_from_the_fallback_model(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, FALLBACK_MODEL="gpt-4.1-mini") as c:
        c.app.state.provider = FlakyProvider(broken="gpt-4o-mini")
        r = ask(c, EASY)
        assert r.status_code == 200
        assert r.headers["X-SentryGate-Failover"] == "gpt-4o-mini"
        line = last_line(tmp_path)
        assert line["failover"] == "gpt-4o-mini" and line["model_used"] == "gpt-4.1-mini"


def test_no_fallback_set_means_the_error_is_returned(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, FALLBACK_MODEL="") as c:
        c.app.state.provider = FlakyProvider(broken="gpt-4o-mini")
        assert ask(c, EASY).status_code == 502
