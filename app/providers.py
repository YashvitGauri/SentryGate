"""Talking to the model, in three modes.

    mock    a fixed reply, no network, no key. Tests and CI use this.
    replay  a reply recorded earlier and saved to disk, matched on the exact
            request. No network, no key, no money.
    live    a real call to OpenAI.

Replay is what keeps the attack sweeps in Week 4 free and repeatable, and it
is why the demo still works when the room has no internet. Record once with
PROVIDER_MODE=live PROVIDER_RECORD=on, then run everything in replay forever.

Every live call passes a daily spend cap first. A sweep is a loop that fires
hundreds of prompts, and a loop with a bug should cost pennies, not a bill.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from app.config import Settings
from app.schemas import ChatCompletionRequest, prompt_hash

# Dollars per million tokens, (input, output).
# Check these against the provider price page before any cost number is
# quoted in the paper. They are here now because the spend cap needs them.
PRICES: dict[str, tuple[float, float]] = {
    # OpenAI direct names.
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    # OpenRouter slugs (same underlying models, same list price). OpenRouter is
    # our provider for the live call; see .env.example.
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4.1-mini": (0.40, 1.60),
}
FALLBACK_PRICE = (1.00, 3.00)  # unknown model: assume dear, so the cap stays safe

MOCK_REPLY = "This is a mock reply from SentryGate. No model was called."


class ProviderError(RuntimeError):
    """Something stopped us answering. Carries the HTTP status to return."""

    status_code = 502
    error_type = "provider_error"
    code: str | None = None


class SpendCapExceeded(ProviderError):
    status_code = 402
    error_type = "spend_cap_exceeded"
    code = "daily_cap"


class CassetteMissing(ProviderError):
    status_code = 503
    error_type = "cassette_missing"
    code = "no_recording"


class UpstreamError(ProviderError):
    status_code = 502
    error_type = "upstream_error"
    code = "provider_call_failed"


@dataclass(frozen=True)
class ProviderResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    source: str  # mock, replay or live


def estimate_tokens(text: str) -> int:
    """Rough token count for the modes that do not get a real one.

    Four characters per token is the usual rule of thumb. Only mock and replay
    use it. Live calls report real numbers, and those are what the paper uses.
    """
    return max(1, len(text) // 4)


def price_for(model: str) -> tuple[float, float]:
    return PRICES.get(model, FALLBACK_PRICE)


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = price_for(model)
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


class SpendLedger:
    """How much we spent today, kept in a small file so a restart cannot reset it."""

    def __init__(self, path: Path, cap_usd: float):
        self.path = path
        self.cap_usd = cap_usd
        self._lock = threading.Lock()

    def _read(self) -> tuple[str, float]:
        try:
            data = json.loads(self.path.read_text())
            return str(data.get("date", "")), float(data.get("spent_usd", 0.0))
        except (OSError, ValueError):
            return "", 0.0

    def _write(self, day: str, spent: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then move it, so a crash mid-write cannot leave
        # a broken ledger behind and quietly reset the cap to zero.
        handle, tmp = tempfile.mkstemp(dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w") as file:
                json.dump({"date": day, "spent_usd": round(spent, 6)}, file)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def spent_today(self) -> float:
        day, spent = self._read()
        return spent if day == date.today().isoformat() else 0.0

    def check(self, estimated_usd: float) -> None:
        """Refuse before the call, not after. Raises SpendCapExceeded."""
        spent = self.spent_today()
        if spent + estimated_usd > self.cap_usd:
            raise SpendCapExceeded(
                f"Daily spend cap reached. Spent ${spent:.4f} today, this call "
                f"needs about ${estimated_usd:.4f}, cap is ${self.cap_usd:.2f}. "
                f"Raise SPEND_CAP_USD_PER_DAY or use PROVIDER_MODE=replay."
            )

    def record(self, actual_usd: float) -> None:
        with self._lock:
            day = date.today().isoformat()
            stored_day, spent = self._read()
            base = spent if stored_day == day else 0.0
            self._write(day, base + actual_usd)


class Provider:
    """What every mode has to do."""

    name = "provider"

    def complete(self, request: ChatCompletionRequest, model: str) -> ProviderResult:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MockProvider(Provider):
    """No network, no key, no money. The default, so a fresh clone just runs."""

    name = "mock"

    def complete(self, request: ChatCompletionRequest, model: str) -> ProviderResult:
        started = time.perf_counter()
        prompt = request.messages[-1].content
        text = f"{MOCK_REPLY} You said: {prompt[:120]}"
        return ProviderResult(
            text=text,
            model=model,
            tokens_in=estimate_tokens(prompt),
            tokens_out=estimate_tokens(text),
            cost_usd=0.0,
            latency_ms=(time.perf_counter() - started) * 1000,
            source="mock",
        )


class ReplayProvider(Provider):
    """Serves a reply recorded earlier. Same request in, same reply out."""

    name = "replay"

    def __init__(self, cassette_dir: Path):
        self.cassette_dir = cassette_dir

    def path_for(self, model: str, request: ChatCompletionRequest) -> Path:
        return self.cassette_dir / f"{prompt_hash(model, request.messages)}.json"

    def complete(self, request: ChatCompletionRequest, model: str) -> ProviderResult:
        started = time.perf_counter()
        path = self.path_for(model, request)
        try:
            data = json.loads(path.read_text())
        except OSError:
            raise CassetteMissing(
                f"No recording for this request under {self.cassette_dir}. "
                f"Record it once with PROVIDER_MODE=live PROVIDER_RECORD=on."
            ) from None
        except ValueError as exc:
            raise CassetteMissing(f"Recording at {path} is not valid JSON: {exc}") from None
        return ProviderResult(
            text=data["text"],
            model=data.get("model", model),
            tokens_in=int(data.get("tokens_in", 0)),
            tokens_out=int(data.get("tokens_out", 0)),
            cost_usd=0.0,  # already paid for when it was recorded
            latency_ms=(time.perf_counter() - started) * 1000,
            source="replay",
        )


class OpenAIProvider(Provider):
    """The real call. Costs money, so the ledger sees it first."""

    name = "live"

    def __init__(self, settings: Settings, ledger: SpendLedger, client: httpx.Client | None = None):
        self.settings = settings
        self.ledger = ledger
        self.record = settings.provider_record
        self.client = client or httpx.Client(
            base_url=settings.openai_base_url,
            timeout=settings.request_timeout_s,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        )

    def complete(self, request: ChatCompletionRequest, model: str) -> ProviderResult:
        prompt_chars = sum(len(m.content) for m in request.messages)
        max_out = request.max_tokens or self.settings.max_output_tokens
        # Worst case: the reply fills max_tokens. Estimate high on purpose.
        self.ledger.check(cost_usd(model, estimate_tokens(" " * prompt_chars), max_out))

        payload = {
            "model": model,
            "messages": [m.model_dump() for m in request.messages],
            "max_tokens": max_out,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        started = time.perf_counter()
        try:
            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise UpstreamError(f"OpenAI returned {exc.response.status_code}: {detail}") from None
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Could not reach OpenAI: {exc}") from None
        except ValueError as exc:
            raise UpstreamError(f"OpenAI reply was not JSON: {exc}") from None

        latency_ms = (time.perf_counter() - started) * 1000
        try:
            text = body["choices"][0]["message"]["content"] or ""
            usage = body.get("usage", {})
            tokens_in = int(usage.get("prompt_tokens", 0))
            tokens_out = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamError(f"OpenAI reply had an unexpected shape: {exc}") from None

        spent = cost_usd(model, tokens_in, tokens_out)
        self.ledger.record(spent)
        result = ProviderResult(
            text=text, model=body.get("model", model), tokens_in=tokens_in,
            tokens_out=tokens_out, cost_usd=spent, latency_ms=latency_ms, source="live",
        )
        if self.record:
            self._save_cassette(request, model, result)
        return result

    def _save_cassette(self, request: ChatCompletionRequest, model: str, result: ProviderResult) -> None:
        path = self.settings.cassette_dir / f"{prompt_hash(model, request.messages)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "model": result.model,
            "text": result.text,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, indent=2))

    def close(self) -> None:
        self.client.close()


def build_provider(settings: Settings) -> Provider:
    if settings.provider_mode == "mock":
        return MockProvider()
    if settings.provider_mode == "replay":
        return ReplayProvider(settings.cassette_dir)
    ledger = SpendLedger(settings.spend_ledger_path, settings.spend_cap_usd_per_day)
    return OpenAIProvider(settings, ledger)
