"""Screen every prompt once, before anything else uses it.

Two signals fold into one Verdict:

- injection score from protectai/deberta-v3-base-prompt-injection-v2
- PII entities from Presidio, with a regex fallback when Presidio is absent

The pipeline is loaded once at startup, never per request. Tests inject a
stub scorer so the suite never downloads 370 MB of weights.
"""

from __future__ import annotations

import re
import time

from app.verdict import Verdict, make_verdict

FILTER_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"

# Same cues as poc_bypass.py --fast, so stub and PoC tell the same story.
_STUB_CUES = ("ignore", "disregard", "forget what", "never mind", "pay no attention", "set aside")
_STUB_TARGETS = (
    "system prompt", "system message", "instructions",
    "setup text", "configuration", "hidden prompt",
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")


class KeywordStubScorer:
    """No models, no network. Used in tests and as a fallback."""

    model_id = "keyword-stub-v0"

    def score(self, prompt: str) -> float:
        lowered = prompt.lower()
        hit = any(c in lowered for c in _STUB_CUES) and any(t in lowered for t in _STUB_TARGETS)
        # Also catch the exact Week-2 demo attack even if wording shifts slightly.
        if "ignore previous instructions" in lowered and "system prompt" in lowered:
            hit = True
        return 1.0 if hit else 0.0


class HuggingFaceScorer:
    """The real deberta classifier. Loaded once, called many times."""

    def __init__(self, model_id: str = FILTER_MODEL):
        from transformers import pipeline  # lazy: keeps `import app.screening` light

        self.pipe = pipeline("text-classification", model=model_id, truncation=True)
        self.model_id = model_id

    def score(self, prompt: str) -> float:
        out = self.pipe(prompt)[0]
        return float(out["score"]) if out["label"] == "INJECTION" else 1.0 - float(out["score"])


SPACY_MODEL = "en_core_web_sm"

# Presidio loads a spaCy model, which is slow. Build the analyzer once and
# reuse it. The old code rebuilt it on every request, which reloaded the model
# every time; on a real workload that alone would dominate the latency.
_PRESIDIO_ENGINE = None
_PRESIDIO_TRIED = False


def _get_presidio():
    """Return a ready AnalyzerEngine, or None if Presidio is not installed.

    Built once and cached. A None result means fall back to the regex scan, so
    the gateway and the tests still run with no spaCy model present.
    """
    global _PRESIDIO_ENGINE, _PRESIDIO_TRIED
    if _PRESIDIO_TRIED:
        return _PRESIDIO_ENGINE
    _PRESIDIO_TRIED = True
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
        from presidio_analyzer.nlp_engine import NlpEngineProvider  # type: ignore

        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
        })
        _PRESIDIO_ENGINE = AnalyzerEngine(nlp_engine=provider.create_engine())
    except Exception:
        _PRESIDIO_ENGINE = None
    return _PRESIDIO_ENGINE


def _regex_pii(prompt: str) -> tuple[bool, tuple[str, ...], str]:
    found: list[str] = []
    if _EMAIL_RE.search(prompt):
        found.append("EMAIL_ADDRESS")
    # Avoid flagging every short number: require at least 9 digits.
    for match in _PHONE_RE.findall(prompt):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 9:
            found.append("PHONE_NUMBER")
            break
    return (len(found) > 0, tuple(found), "regex-fallback-v0")


def analyze_pii(prompt: str) -> tuple[bool, tuple[str, ...], str]:
    """Return (has_pii, entity_types, analyzer_version).

    Uses Presidio when it is installed, and the email/phone regex otherwise, so
    the gateway and the tests run with or without the spaCy model.
    """
    engine = _get_presidio()
    if engine is None:
        return _regex_pii(prompt)
    try:
        results = engine.analyze(text=prompt, language="en")
        entities = tuple(sorted({r.entity_type for r in results}))
        return (len(entities) > 0, entities, f"presidio+{SPACY_MODEL}")
    except Exception:
        return _regex_pii(prompt)


class Screener:
    """Owns the scorer. One instance lives on app.state for the process."""

    def __init__(self, scorer=None, threshold: float = 0.5):
        self.scorer = scorer or KeywordStubScorer()
        self.threshold = float(threshold)
        self.scorer_id = getattr(self.scorer, "model_id", type(self.scorer).__name__)

    def screen(self, prompt: str) -> Verdict:
        score = float(self.scorer.score(prompt))
        has_pii, entities, pii_version = analyze_pii(prompt)
        return make_verdict(
            injection_score=score,
            threshold=self.threshold,
            has_pii=has_pii,
            pii_entities=entities,
            prompt=prompt,
            model_versions={"injection": self.scorer_id, "pii": pii_version},
        )


def build_screener(settings, scorer=None) -> tuple[Screener, dict]:
    """Build the process-wide screener. Never raises for a missing model.

    Modes from SCREENING_SCORER env (via settings):
    - stub: always the keyword scorer, fastest, for tests
    - hf: force the real model, raises if it cannot load
    - auto: try the real model, fall back to stub with a reason
    """
    started = time.perf_counter()
    mode = getattr(settings, "screening_scorer", "auto")
    threshold = getattr(settings, "injection_threshold", 0.5)

    if scorer is not None:
        return Screener(scorer=scorer, threshold=threshold), {
            "mode": "injected",
            "scorer": getattr(scorer, "model_id", type(scorer).__name__),
            "load_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    if mode == "stub":
        screener = Screener(scorer=KeywordStubScorer(), threshold=threshold)
        return screener, {
            "mode": "stub",
            "scorer": screener.scorer_id,
            "load_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    # auto: try HF once, fall back to stub so the gateway always starts.
    try:
        screener = Screener(scorer=HuggingFaceScorer(), threshold=threshold)
        return screener, {
            "mode": "hf",
            "scorer": screener.scorer_id,
            "load_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        screener = Screener(scorer=KeywordStubScorer(), threshold=threshold)
        info = {
            "mode": "stub-fallback",
            "scorer": screener.scorer_id,
            "load_ms": round((time.perf_counter() - started) * 1000, 2),
            "fallback_reason": f"{type(exc).__name__}: {str(exc)[:160]}",
        }
        if mode == "hf":
            raise RuntimeError(f"SCREENING_SCORER=hf but model failed to load: {exc}") from exc
        return screener, info
