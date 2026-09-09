"""The safety result that travels with a request.

Computed once at screening time, stored next to the cached answer in Week 3,
and checked on every cache lookup in Phase 3. The shape is frozen here because
changing it later would invalidate already-collected logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


INTENTS = ("informational", "credentials", "tool_use", "pii", "other")
RISK_LEVELS = ("low", "medium", "high")

_CREDENTIAL_CUES = (
    "password", "passwd", "api key", "apikey", "secret",
    "client secret", "credentials", "login", "sign in",
    "credit card", "card number",
)

_TOOL_CUES = (
    "run ", "execute", "shell", "bash", "powershell",
    "sudo", "rm -rf", "delete", "drop table", "select ",
    "insert into", "<script", "curl ", "wget ",
    "ignore previous instructions", "disregard",
    "reveal the system prompt", "system prompt",
)

_INFORMATIONAL_CUES = (
    "what ", "why ", "how ", "when ", "where ", "who ",
    "what is", "explain", "capital of", "define", "tell me",
)


def classify_intent(prompt: str, has_pii: bool = False) -> str:
    """Cheap keyword buckets. Upgraded to a classifier later without changing schema."""
    lowered = prompt.lower()
    if any(cue in lowered for cue in _CREDENTIAL_CUES):
        return "credentials"
    if any(cue in lowered for cue in _TOOL_CUES):
        return "tool_use"
    if has_pii:
        return "pii"
    if any(cue in lowered for cue in _INFORMATIONAL_CUES):
        return "informational"
    return "other"


def assess_risk(is_injection: bool, has_pii: bool, intent: str) -> str:
    if is_injection:
        return "high"
    if has_pii or intent in ("credentials", "tool_use", "pii"):
        return "medium"
    return "low"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Verdict:
    is_injection: bool
    injection_score: float  # 0..1, raw classifier output
    has_pii: bool
    pii_entities: tuple[str, ...]  # Presidio types, e.g. ("EMAIL_ADDRESS",)
    intent: str  # informational | credentials | tool_use | pii | other
    risk_level: str  # low | medium | high
    screened_at: str  # ISO-8601 UTC
    model_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_injection": self.is_injection,
            "injection_score": round(float(self.injection_score), 4),
            "has_pii": self.has_pii,
            "pii_entities": list(self.pii_entities),
            "intent": self.intent,
            "risk_level": self.risk_level,
            "screened_at": self.screened_at,
            "model_versions": dict(self.model_versions),
        }

    @property
    def clean(self) -> bool:
        return not self.is_injection


def make_verdict(
    injection_score: float,
    threshold: float,
    has_pii: bool,
    pii_entities: tuple[str, ...] = (),
    prompt: str = "",
    model_versions: dict[str, str] | None = None,
) -> Verdict:
    is_injection = float(injection_score) >= float(threshold)
    intent = classify_intent(prompt, has_pii)
    risk = assess_risk(is_injection, has_pii, intent)
    return Verdict(
        is_injection=is_injection,
        injection_score=float(injection_score),
        has_pii=has_pii,
        pii_entities=tuple(pii_entities),
        intent=intent,
        risk_level=risk,
        screened_at=_now_iso(),
        model_versions=dict(model_versions or {}),
    )
