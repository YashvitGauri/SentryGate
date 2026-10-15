"""The gateway.

Passes an OpenAI-shaped request through the cache and screening, then to the
model, and writes one line about it to the request log. Week 3 is the
vulnerable baseline: cache_first checks the cache before screening, and the
lookup ignores the stored verdict.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.cache import SemanticCache, build_cache
from app.config import Settings, get_settings
from app.logging_mw import JsonlWriter, RequestLogMiddleware
from app.providers import Provider, ProviderError, UpstreamError, build_provider, estimate_tokens
from app.mitigations.output_guard import scan as scan_output
from app.mitigations.rate_limit import build_rate_limiter
from app.router import route
from app.schemas import (
    ChatCompletionRequest,
    ChatMessage,
    ChatCompletionResponse,
    ErrorResponse,
    prompt_hash,
    user_prompt,
)
from app.screening import build_screener
from app.verdict import classify_intent

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.screener, app.state.screening_info = build_screener(settings)
    app.state.cache, app.state.cache_info = build_cache(settings)
    app.state.rate_limiter, app.state.rate_limit_info = build_rate_limiter(settings)
    app.state.log_writer = JsonlWriter(settings.log_path)
    app.state.log_config = runtime_log_config(
        settings, app.state.screening_info, app.state.cache_info
    )
    yield
    app.state.provider.close()
    app.state.log_writer.close()


def runtime_log_config(settings: Settings, screening_info: dict, cache_info: dict) -> dict:
    """The settings, plus the parts that actually loaded.

    A stand-in and a real model produce very different numbers. Every log line
    has to say which one was running, or no result can be trusted.
    """
    config = settings.as_log_dict()
    config["scorer"] = screening_info.get("scorer", "unknown")
    config["embedder"] = (cache_info.get("embedder") or {}).get("model", "unknown")
    config["cache_backend"] = cache_info.get("backend", "unknown")
    return config


app = FastAPI(title="SentryGate", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)


def _error(status: int, message: str, type_: str, code: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse.build(message, type_, code))


def _note_refusal(request: Request, reason: str) -> None:
    """Say in the log why a request did not get an answer."""
    record = getattr(request.state, "record", None)
    if record is not None:
        record.block_reason = reason


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    _note_refusal(request, exc.error_type)
    return _error(exc.status_code, str(exc), exc.error_type, exc.code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # OpenAI clients expect an error object, not FastAPI's default detail list.
    _note_refusal(request, "invalid_request")
    return _error(400, str(exc.errors()), "invalid_request_error", "bad_request")


@app.get("/healthz")
def healthz() -> dict:
    settings: Settings = app.state.settings
    cache_info = getattr(app.state, "cache_info", {"backend": "unknown"})
    try:
        cache_info = dict(cache_info)
        cache_info["size"] = app.state.cache.size()
    except Exception:
        pass
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "provider_mode": settings.provider_mode,
        "default_model": settings.default_model,
        "build_sha": settings.build_sha,
        "log_path": str(settings.log_path),
        "config": getattr(app.state, "log_config", None) or settings.as_log_dict(),
        "screening": getattr(app.state, "screening_info", {"mode": "unknown"}),
        "cache": cache_info,
        "cache_seed_enabled": settings.allow_cache_seed,
        "rate_limit": getattr(app.state, "rate_limit_info", {}),
    }


@app.get("/metrics/summary")
def metrics_summary() -> dict:
    """The real traffic so far, read from the request log. For the live demo."""
    from app.metrics import summarise_file

    settings: Settings = app.state.settings
    summary = summarise_file(settings.log_path)
    summary["config"] = getattr(app.state, "log_config", None) or settings.as_log_dict()
    return summary


@app.post("/v1/cache/clear")
def cache_clear() -> dict:
    """Reset between experiments. Doing it by hand corrupts results."""
    cleared = app.state.cache.clear()
    app.state.cache_info["size"] = app.state.cache.size()
    return {"cleared": cleared}


class SeedRequest(BaseModel):
    prompt: str = Field(min_length=1)
    response: str = Field(min_length=1)
    model: str | None = None
    # Optional. Without it, the real screener scores the prompt and that
    # verdict is stored, exactly as a normal miss would store it.
    verdict: dict | None = None


@app.post("/v1/cache/seed")
def cache_seed(body: SeedRequest) -> JSONResponse:
    """Plant an entry directly. Test-only, for the Week 4 poisoning experiment.

    The paper's threat model says a poisoned entry gets into the cache somehow.
    This is how an experiment models that, without pretending the route in
    matters to what is measured: whether the entry gets served.
    """
    settings: Settings = app.state.settings
    if not settings.allow_cache_seed:
        # Look exactly like a missing route while it is off.
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    model = body.model or settings.default_model
    messages = [ChatMessage(role="user", content=body.prompt)]
    verdict = body.verdict
    if verdict is None:
        verdict = app.state.screener.screen(body.prompt).to_dict()
    entry_id = app.state.cache.store(
        prompt=body.prompt,
        prompt_hash=prompt_hash(model, messages),
        response=body.response,
        model=model,
        verdict=verdict,
    )
    return JSONResponse(content={"entry_id": entry_id, "verdict": verdict})


def _serve_hit(payload: dict, similarity: float, matched_id: str) -> ChatCompletionResponse:
    return ChatCompletionResponse.build(
        text=payload["response"],
        model=payload.get("model", "unknown"),
        tokens_in=estimate_tokens(payload.get("prompt_text", "")),
        tokens_out=estimate_tokens(payload.get("response", "")),
    )


def _screen_prompt(request: Request, response: Response, prompt: str):
    """Run the classifier once. Returns the verdict, sets headers and log."""
    record = request.state.record
    with record.stage("screen"):
        verdict = request.app.state.screener.screen(prompt)
    record.screening_ran = True
    record.verdict = verdict.to_dict()
    response.headers["X-SentryGate-Screened"] = "true"
    response.headers["X-SentryGate-Verdict"] = "blocked" if verdict.is_injection else "clean"
    response.headers["X-SentryGate-Injection-Score"] = f"{verdict.injection_score:.3f}"
    return verdict


def _blocked_response(request: Request, verdict) -> JSONResponse:
    record = request.state.record
    record.block_reason = "prompt_injection"
    blocked = _error(
        403,
        f"Blocked by SentryGate screening (injection score {verdict.injection_score:.3f}).",
        "sentrygate_blocked",
        "prompt_injection",
    )
    blocked.headers["X-SentryGate-Screened"] = "true"
    blocked.headers["X-SentryGate-Verdict"] = "blocked"
    blocked.headers["X-SentryGate-Injection-Score"] = f"{verdict.injection_score:.3f}"
    blocked.headers["X-SentryGate-Cache"] = record.cache_outcome
    return blocked


def _rate_limited(request: Request, decision) -> JSONResponse:
    _note_refusal(request, decision.reason)
    what = "requests per minute" if decision.reason == "rate_limited" else "model tokens per day"
    refused = _error(429, f"Too many {what} for this key (limit {decision.limit}). "
                          f"Try again in {decision.retry_after_s} s.", "rate_limit_exceeded", decision.reason)
    refused.headers["Retry-After"] = str(decision.retry_after_s)
    refused.headers["X-RateLimit-Limit"] = str(decision.limit)
    refused.headers["X-RateLimit-Remaining"] = "0"
    return refused


def _guard_output(request: Request, response: Response, text: str) -> JSONResponse | None:
    """Phase 3 output guard. Returns a refusal in block mode, else None."""
    settings: Settings = request.app.state.settings
    if settings.output_guard == "off":
        return None
    record = request.state.record
    flags = scan_output(text)
    record.output_flags = flags
    if not flags:
        return None
    if settings.output_guard == "flag":
        response.headers["X-SentryGate-Output-Flags"] = ",".join(flags)
        return None
    _note_refusal(request, "unsafe_output")
    refused = _error(403, f"Answer withheld by SentryGate: it contained {', '.join(flags)}.",
                     "sentrygate_blocked", "unsafe_output")
    refused.headers["X-SentryGate-Output-Flags"] = ",".join(flags)
    refused.headers["X-SentryGate-Cache"] = record.cache_outcome
    return refused


# Kinds of question where a wrong cached answer does the most damage.
HIGH_RISK_INTENTS = ("credentials", "tool_use", "pii")


def _cache_policy(settings: Settings, prompt: str):
    """Decide what a stored answer must carry to be served for this question.

    Returns (cheap_intent, require, threshold). The baseline returns no
    requirement and the global threshold: any similar answer is served, which
    is the hole. With the Phase 3 defence the question gets a cheap label from
    keyword rules, which costs almost nothing, so the cache can stay in front
    of the slow safety check. A stored answer is then served only if its saved
    label says it was not an attack and is the same kind of question, and
    risky kinds need a closer match.
    """
    if not (settings.cache_verdict_filter or settings.cache_reverify_high_risk):
        return None, None, settings.sim_threshold
    cheap_intent = classify_intent(prompt)
    if not settings.cache_verdict_filter:
        return cheap_intent, None, settings.sim_threshold
    threshold = settings.cache_strict_threshold if cheap_intent in HIGH_RISK_INTENTS else settings.sim_threshold
    return cheap_intent, {"is_injection": False, "label_intent": cheap_intent}, threshold


def _needs_recheck(settings: Settings, cheap_intent: str | None, payload: dict | None) -> bool:
    """Should a cache hit go through the full safety check before it is served?

    Only when re-checking is on. With REVERIFY_SCOPE=all, every hit is
    checked. With risky (the default), only the hits most likely to be wrong:
    a risky kind of question, or an answer that was a close call (or flagged)
    when it was saved. Everything else keeps the speed of a hit.
    """
    if not settings.cache_reverify_high_risk:
        return False
    if settings.reverify_scope == "all":
        return True
    payload = payload or {}
    return (
        cheap_intent in HIGH_RISK_INTENTS
        or bool(payload.get("is_injection"))
        or float(payload.get("injection_score", 0.0)) >= settings.reverify_score
    )


def _lookup_cache(request: Request, prompt: str, prompt_hash_value: str, threshold: float,
                  require: dict | None = None, cheap_intent: str | None = None):
    """Embed and search. Records outcome, similarity and timings on the log."""
    record = request.state.record
    cache: SemanticCache = request.app.state.cache
    with record.stage("embed"):
        vector = cache.embedder.embed(prompt)
    with record.stage("cache"):
        result = cache.lookup_with_vector(prompt_hash_value, vector, require, threshold)
    record.cache_outcome = "hit" if result.hit else "miss"
    record.cache_similarity = result.similarity
    record.cache_matched_id = result.matched_id
    record.cache_threshold = threshold
    record.cache_filter = require is not None
    record.cheap_intent = cheap_intent
    return result, vector


# Sync on purpose. FastAPI runs a plain def in a worker thread, so blocking
# provider, classifier and embedding calls cannot stall the server.
@app.post("/v1/chat/completions", response_model=None)
def chat_completions(
    body: ChatCompletionRequest, request: Request, response: Response
) -> ChatCompletionResponse | JSONResponse:
    settings: Settings = app.state.settings
    record = request.state.record

    if body.stream:
        raise StreamingNotSupported()

    limiter = request.app.state.rate_limiter
    if limiter.enabled:
        decision = limiter.check(record.api_key_id)
        if not decision.allowed:
            return _rate_limited(request, decision)
        if decision.limit:
            response.headers["X-RateLimit-Limit"] = str(decision.limit)
            response.headers["X-RateLimit-Remaining"] = str(decision.remaining)

    model = body.model or settings.default_model
    prompt = user_prompt(body.messages)
    prompt_hash_value = prompt_hash(model, body.messages)

    record.model_requested = body.model
    record.prompt_hash = prompt_hash_value
    record.prompt_len = len(prompt)

    if settings.pipeline_order == "cache_first":
        cheap_intent, require, threshold = _cache_policy(settings, prompt)
        result, _ = _lookup_cache(request, prompt, prompt_hash_value, threshold, require, cheap_intent)
        if result.hit:
            if _needs_recheck(settings, cheap_intent, result.payload):
                # Phase 3: a risky or close-call hit pays for the full check.
                record.reverified = True
                verdict = _screen_prompt(request, response, prompt)
                if verdict.is_injection:
                    return _blocked_response(request, verdict)
            else:
                # Baseline behaviour: served with screening_ran=False.
                response.headers["X-SentryGate-Screened"] = "false"
                response.headers["X-SentryGate-Verdict"] = "unscreened"
            refused = _guard_output(request, response, (result.payload or {}).get("response", ""))
            if refused is not None:
                return refused
            hit_response = _serve_hit(result.payload or {}, result.similarity, result.matched_id or "")
            record.model_used = (result.payload or {}).get("model", model)
            record.provider_source = "cache"
            record.tokens_in = estimate_tokens(prompt)
            record.tokens_out = estimate_tokens((result.payload or {}).get("response", ""))
            record.cost_usd = 0.0
            response.headers["X-SentryGate-Provider"] = "cache"
            response.headers["X-SentryGate-Cache"] = "hit"
            response.headers["X-SentryGate-Similarity"] = f"{result.similarity:.3f}"
            return hit_response
        verdict = _screen_prompt(request, response, prompt)
        if verdict.is_injection:
            return _blocked_response(request, verdict)
        return _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict)

    # screen_first: the comparison arm. Screening always runs, even on a hit.
    verdict = _screen_prompt(request, response, prompt)
    if verdict.is_injection:
        return _blocked_response(request, verdict)
    result, _ = _lookup_cache(request, prompt, prompt_hash_value, settings.sim_threshold)
    if result.hit:
        refused = _guard_output(request, response, (result.payload or {}).get("response", ""))
        if refused is not None:
            return refused
        hit_response = _serve_hit(result.payload or {}, result.similarity, result.matched_id or "")
        record.model_used = (result.payload or {}).get("model", model)
        record.provider_source = "cache"
        record.tokens_in = estimate_tokens(prompt)
        record.tokens_out = estimate_tokens((result.payload or {}).get("response", ""))
        record.cost_usd = 0.0
        response.headers["X-SentryGate-Provider"] = "cache"
        response.headers["X-SentryGate-Cache"] = "hit"
        response.headers["X-SentryGate-Similarity"] = f"{result.similarity:.3f}"
        return hit_response
    return _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict)


def _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict):
    settings: Settings = request.app.state.settings
    provider: Provider = request.app.state.provider
    cache: SemanticCache = request.app.state.cache
    record = request.state.record
    decision = route(settings, body.model, prompt)
    record.route = decision.to_log()
    with record.stage("provider"):
        try:
            result = provider.complete(body, decision.model)
        except UpstreamError:
            # One retry on the fallback model. A spend-cap refusal is not an
            # UpstreamError, so it never fails over to spend more.
            fallback = settings.fallback_model
            if not fallback or fallback == decision.model:
                raise
            record.failover = decision.model
            result = provider.complete(body, fallback)
            response.headers["X-SentryGate-Failover"] = decision.model
    if decision.tier != "fixed":
        response.headers["X-SentryGate-Route"] = decision.tier
    record.model_used = result.model
    record.provider_source = result.source
    record.tokens_in = result.tokens_in
    record.tokens_out = result.tokens_out
    record.cost_usd = result.cost_usd
    request.app.state.rate_limiter.spend(record.api_key_id, result.tokens_in + result.tokens_out)
    refused = _guard_output(request, response, result.text)
    if refused is not None:
        return refused  # paid for, but never served and never saved to the cache
    with record.stage("cache_store"):
        cache.store(
            prompt=prompt,
            prompt_hash=prompt_hash_value,
            response=result.text,
            model=result.model,
            verdict=record.verdict,
        )
    response.headers["X-SentryGate-Provider"] = result.source
    response.headers["X-SentryGate-Cache"] = "miss"
    return ChatCompletionResponse.build(
        text=result.text,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )


class StreamingNotSupported(ProviderError):
    status_code = 400
    error_type = "invalid_request_error"
    code = "stream_not_supported"

    def __init__(self) -> None:
        super().__init__(
            "SentryGate does not stream yet. Send stream=false. "
            "Streaming and caching interact, so it lands after the cache is real."
        )
