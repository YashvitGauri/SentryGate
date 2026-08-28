# Phase 2 — Gateway + reproduce the bypass on our own system

**Window:** 23 Aug – 26 Sep (5 weeks). **Assessed at:** Progress Eval-1.
**Parent plan:** [`001-introfile.md`](001-introfile.md). This file is the
implementation-level plan for the Phase 2 rows in it.

| Week | Dates | Ships |
|---|---|---|
| 1 | 23–29 Aug | Gateway skeleton — a real request reaches a real model through us |
| 2 | 30 Aug – 5 Sep | Screening layer — every prompt gets a `Verdict` |
| 3 | 6–12 Sep | Baseline semantic cache — deliberately vulnerable |
| 4 | 13–19 Sep | **Reproduce the bypass on our own gateway** — the phase's real result |
| 5 | 20–26 Sep | Logging completed, figures, demo hardening |

> **Schedule reality:** Week 1 has ~2 days left as this is written. Section
> "Start here" at the bottom is the shortest path to a Week-1 artifact.

---

## What Phase 2 must produce

One sentence for the reviewer:

> *"On our own running gateway, N% of reworded attacks were served from a
> poisoned cache entry, and the filter ran zero times while it happened."*

Phase 1 asserted that ordering by construction — `SemanticCache.lookup()` simply
never called the filter. Phase 2 has to **earn** the same number on a real
FastAPI service talking to a real model with a real vector store. Everything
below exists to make that one sentence defensible.

Secondary, but non-negotiable: the JSONL request log. Every metric in Phases 3
and 4 — cost saved, p99 latency, ablation deltas, the bypass-vs-hit-ratio
trade-off chart — is a query over that file. If it is not written correctly from
Week 1, those phases have no data source.

---

## Five decisions to lock before writing code

These are the choices that are cheap now and expensive in October.

### 1. The vulnerability is a config flag, not a code version

Do **not** build "the vulnerable cache" in Phase 2 and then rewrite it in
Phase 3. Build one cache with a switch:

```
PIPELINE_ORDER=cache_first|screen_first     # cache_first = industry standard = the hole
CACHE_VERDICT_FILTER=off|on                 # on = the contribution
CACHE_REVERIFY_HIGH_RISK=off|on             # Phase 3 Week 2
```

Phase 2 ships with `cache_first` / filter `off`. Phase 3 Week 1 flips one flag
and adds one Qdrant filter clause. Consequences:

- The baseline-vs-hardened comparison is the *same binary*, same commit, same
  data — no "you changed other things too" objection.
- Phase 4's ablation table (§ Phase 4 Week 2 of the parent plan) is already
  built. Each flag is one ablation arm.

### 2. Write the verdict into the cache payload from Week 3, even though nothing reads it

Week 3's cache is supposed to be vulnerable, so it must not *filter* on the
verdict. It should still **store** it. Storing costs nothing, and it means
Phase 3 is a query change rather than a re-index of every cached entry.

### 3. Logging moves from Week 5 to Week 1 (deviation from the parent plan)

The parent plan puts `logging_mw.py` in Week 5. That is too late: Week 4's
headline claim is *"the filter ran zero times"*, and the only credible evidence
for that is a request log showing no screening event. Ship a minimal middleware
in Week 1 (request id, timing, outcome), enrich it in Week 5 (resolved cost,
token counts). Week 5 keeps the same deliverable; it just stops being the file's
first appearance.

### 4. Providers need a replay mode

Phase 1's proudest property is that the demo runs with the network switched off.
Week 1 breaks that by design — but the *demo* must not depend on OpenAI being up
and the department Wi-Fi behaving. `providers.py` gets three modes:

```
PROVIDER_MODE=live      # real API call, costs money
PROVIDER_MODE=replay    # replays a recorded cassette keyed by prompt hash
PROVIDER_MODE=mock      # fixed canned reply, no I/O, for tests
```

`replay` doubles as the Phase 4 reproducibility story: `make eval` regenerates
every figure from cassettes without spending a cent or needing a key.

### 5. Spend cap on day one

Real keys enter the repo's workflow this week. The denial-of-wallet mitigation
is scheduled for Phase 3 Week 4, but a *developer-side* cap is needed
immediately: a hard `SPEND_CAP_USD_PER_DAY` checked in `providers.py` that
raises before the call. An attack-variant sweep is a loop that fires hundreds of
prompts; one bad loop against a frontier model is a real bill.

---

## Frozen contracts

Changing these later invalidates already-collected logs, so they are decided
here, once.

### `Verdict` — computed once at screening, travels with the request

```python
@dataclass(frozen=True)
class Verdict:
    is_injection: bool
    injection_score: float          # 0..1, raw classifier output
    has_pii: bool
    pii_entities: tuple[str, ...]   # Presidio entity types, e.g. ("EMAIL_ADDRESS",)
    intent: str                     # informational | credentials | tool_use | pii | other
    risk_level: str                 # low | medium | high
    screened_at: str                # ISO-8601 UTC
    model_versions: dict[str, str]  # {"injection": "...v2", "pii": "presidio-2.2.x"}
```

`intent` is the field Phase 3's intent-dependent thresholds key off. It is
cheap to populate in Week 2 (keyword/heuristic buckets) and can be upgraded to a
classifier later without changing the schema.

### Qdrant payload — flat, because Qdrant filters on flat keys

| Key | Type | Why |
|---|---|---|
| `prompt_text` | str | debugging + attack forensics |
| `prompt_hash` | str | sha256, joins to Redis exact-match layer |
| `response` | str | what a hit serves |
| `model` | str | which model produced it |
| `is_injection`, `has_pii` | bool | Phase 3 filter predicate |
| `intent`, `risk_level` | str | Phase 3 filter predicate + thresholds |
| `injection_score` | float | threshold sweeps after the fact |
| `embed_model` | str | invalidate the collection if it changes |
| `created_at` | str | TTL, cache-age analysis |

**The Phase 3 hit predicate, written down now so Week 3 can be measured against
it:** a hit counts only if
`sim >= threshold(incoming.intent)` **and** `stored.is_injection == incoming.is_injection`
**and** `stored.intent == incoming.intent` **and** (`incoming.risk_level != "high"`
or re-verification passed).

### JSONL request log — one line per request

```json
{"ts":"...","request_id":"...","api_key_id":"sha256:8chars",
 "model_requested":"gpt-4o-mini","model_used":"gpt-4o-mini",
 "prompt_hash":"...","prompt_len":42,
 "verdict":{"is_injection":false,"injection_score":0.01,"has_pii":false,
            "intent":"informational","risk_level":"low"},
 "screening_ran":true,
 "cache":{"outcome":"hit|miss|bypassed","similarity":0.94,
          "matched_id":"...","threshold":0.85},
 "latency_ms":{"total":812,"screen":61,"embed":9,"cache":4,"provider":730},
 "tokens":{"in":18,"out":204},"cost_usd":0.00031,
 "status":200,"block_reason":null,
 "config":{"pipeline_order":"cache_first","verdict_filter":"off",
           "reverify":"off","router":"fixed","build_sha":"414f823"}}
```

Two fields carry disproportionate weight:

- **`screening_ran`** — this is the Week 4 claim, as data.
- **`config`** — every line self-describes the experiment arm that produced it.
  Phase 4 ablations become a `group by config` instead of five separate log files
  someone has to remember the provenance of.

### HTTP surface

`POST /v1/chat/completions`, OpenAI-compatible request and response body, so any
OpenAI client (and Locust in Phase 4) points at us by changing a base URL only.
SentryGate's own telemetry rides in **headers**, keeping the body compatible:

```
X-SentryGate-Cache: hit|miss
X-SentryGate-Similarity: 0.942
X-SentryGate-Verdict: clean|blocked
X-SentryGate-Screened: true|false
X-SentryGate-Request-Id: ...
```

Blocked → `403` with an OpenAI-shaped error object
(`{"error":{"type":"sentrygate_blocked","code":"prompt_injection", ...}}`).
Also: `GET /healthz` (models loaded, Qdrant/Redis reachable) and
`GET /metrics/summary` (counters, for the live demo).

---

## Target layout at the end of Phase 2

```
app/
  main.py         # FastAPI app, routes, startup model warmup
  config.py       # env-backed settings incl. every flag in decision 1
  schemas.py      # OpenAI-compatible pydantic models
  verdict.py      # the Verdict dataclass + intent/risk rules
  screening.py    # deberta injection score + Presidio PII -> Verdict
  cache.py        # embed, Redis exact layer, Qdrant semantic layer
  providers.py    # OpenAI/Anthropic + live|replay|mock, spend cap
  logging_mw.py   # the JSONL line above
attacks/
  generate_variants.py   # dataset seeds + surface mutators -> variants.jsonl
  run_bypass.py          # poison, fire, sweep thresholds, emit results.csv
eval/
  make_figures.py        # reads JSONL -> figures (starts in W4, finished P4)
tests/
  test_smoke.py test_screening.py test_cache.py test_bypass.py
data/
  cassettes/     # provider replay
  variants.jsonl results.csv
deploy/
  nginx.conf  Dockerfile.gateway
```

`poc_bypass.py` stays exactly where it is and is not refactored into `app/`.
The deck quotes its captured output; touching it invalidates
`docs/captures/demo-output.txt`.

---

## Week 1 (23–29 Aug) — Gateway skeleton

**Build:** `config.py`, `schemas.py`, `providers.py` (all three modes + spend
cap), `logging_mw.py` (minimal), `main.py` with `/v1/chat/completions`,
`/healthz`; `deploy/Dockerfile.gateway`, `deploy/nginx.conf`; compose gains
`gateway` + `nginx` services alongside the existing `qdrant`/`redis`.

No screening, no cache yet — the request goes straight through to the provider.

**Done when:**
- [ ] `docker compose up -d` brings up nginx → gateway → (qdrant, redis idle)
- [ ] `curl localhost:8080/v1/chat/completions -d '{...}'` returns a real reply
- [ ] the same call with `PROVIDER_MODE=mock` works with the network off
- [ ] one JSONL line per request, with `latency_ms.total` and `config`
- [ ] `/healthz` is green; `pytest tests/test_smoke.py` passes in CI-less local run
- [ ] `make gateway-up`, `make gateway-logs`, `make smoke` exist

**Demo artifact:** terminal capture of the curl and the resulting log line.

**Watch out for:** the `Makefile`'s `PY = ./.venv/Scripts/python.exe` is a
Windows path and there is no `.venv` on every machine. Phase 2 targets should go
through Docker (`docker compose run`), not `$(PY)`, so the gateway is
buildable on all three team members' machines.

---

## Week 2 (30 Aug – 5 Sep) — Screening layer

**Build:** `screening.py` — the deberta pipeline loaded **once at startup**
(never per request), Presidio analyzer, both folded into `Verdict`. Wire into
`main.py` in front of the provider call. `verdict.py` holds the intent buckets
and risk rules. Log gains `verdict` and `latency_ms.screen`.

**Done when:**
- [ ] models load at startup; `/healthz` reports load time and model versions
- [ ] benign prompt → `verdict.clean`, `200`, reply
- [ ] `"ignore previous instructions..."` → `403`, score in the header and log
- [ ] Presidio flags an email/phone in a prompt and sets `has_pii`
- [ ] screening adds < ~150 ms warm (measure it; it is a paper number)
- [ ] `tests/test_screening.py` uses a **stub scorer** — the suite must not need
      370 MB of weights to run

**Demo artifact:** two live curls, clean vs blocked, with the classifier score.

**Watch out for:** Presidio pulls spaCy and a language model; it is the reason
the parent plan pins **Python 3.11**. Budget an afternoon for the install and
pin exact versions into `requirements-gateway.txt` the day it works.

---

## Week 3 (6–12 Sep) — Baseline semantic cache

**Build:** `cache.py` — two layers: Redis exact-match on `prompt_hash` (free,
instant) and Qdrant semantic search on the MiniLM embedding. Collection
bootstrap on startup (384-dim, cosine). Upsert the full payload from the
contract above, verdict included. Lookup uses a **plain global threshold, no
verdict filter** — this is the vulnerable baseline, on purpose, behind the flags
from decision 1. Log gains the `cache` block and `latency_ms.embed/cache`.

**Done when:**
- [ ] first ask ≈ provider latency; same question reworded ≈ tens of ms
- [ ] `X-SentryGate-Cache: hit` and the similarity are visible on the response
- [ ] the Qdrant payload contains a full verdict for every entry (inspect one)
- [ ] a `sentrygate.cache.clear` / `make cache-reset` path exists — experiments
      need a clean cache between runs, and doing it by hand will corrupt a result
- [ ] `tests/test_cache.py` runs against a throwaway collection, not the dev one

**Demo artifact:** the latency drop, on screen, with the hit header.

---

## Week 4 (13–19 Sep) — Reproduce the bypass ⭐

This is the highest-value week in the phase. Everything before it is
infrastructure for this number.

**Build:**
- `attacks/generate_variants.py` — seeds from `deepset/prompt-injections` and
  `jayavibhav/prompt-injection`; two variant families, kept separate because
  Phase 1 showed they behave completely differently:
  - **surface** — casing, punctuation, filler words (free for an attacker)
  - **rewrite** — paraphrases (semantically distant, mostly fail to match)
  Emits `data/variants.jsonl` with `{seed_id, family, text}`.
- `attacks/run_bypass.py` — for each seed: clear cache, poison one entry, fire
  every variant **at the live gateway over HTTP**, sweep
  `SIM_THRESHOLD ∈ {0.95 … 0.65}`, and read the gateway's JSONL to confirm
  `screening_ran == false` on each served hit. Emits `data/results.csv`.
- first chart in `eval/make_figures.py`: bypass rate vs threshold, split by
  family — the Phase 1 sweep table, now measured end to end.

**Done when:**
- [ ] a bypass-success-rate number exists, per family, per threshold, over
      ≥ 50 seeds (not the 1 seed of Phase 1)
- [ ] every claimed bypass is backed by a log line with `screening_ran: false`
- [ ] `results.csv` and the figure regenerate from committed scripts
- [ ] the run is repeatable: `make bypass` end to end from a clean cache

**Demo artifact:** the number, the chart, and one log line proving zero
screening. **This is the slide.**

**Watch out for:** running the sweep in `PROVIDER_MODE=live` is what burns
money. Poisoning and lookup need no provider call at all — only cache misses do.
Run the suite in `replay`, and record the cassettes once.

---

## Week 5 (20–26 Sep) — Logging completed, figures, hardening

**Build:** cost resolution (per-model price table → `cost_usd` per request),
token counts from provider responses, p50/p99 latency split by hit/miss in
`make_figures.py`, `/metrics/summary` for the live demo, regenerated
`docs/architecture.mmd` with the real component names, and a screen recording of
the full demo as the on-stage fallback (the Phase 1 lesson).

**Done when:**
- [ ] every field in the JSONL contract is populated for real
- [ ] `make eval` regenerates the phase's figures from logs, nothing hand-made
- [ ] architecture diagram matches what actually runs
- [ ] README plan table updated: Phase 2 → **done**
- [ ] recorded fallback exists at `docs/captures/`

---

## Testing

| Level | What | Runs without models? |
|---|---|---|
| unit | verdict rules, intent buckets, cost maths, payload shape | yes |
| unit | screening with a stub scorer injected | yes |
| integration | cache put/lookup against a throwaway Qdrant collection | needs compose |
| integration | full request through the gateway in `PROVIDER_MODE=mock` | needs compose |
| experiment | `run_bypass.py` on a 3-seed smoke subset | needs compose |

The rule that matters: **the default `pytest` run must not download a model or
call an API.** Dependency-injected scorers and `PROVIDER_MODE=mock` are how.

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Presidio/spaCy install fights Python version | blocks Week 2 | Docker-first; pin versions the day it works; 3.11 only |
| API spend during sweeps | real money | spend cap (decision 5) + `replay` mode for experiments |
| Model cold start makes the demo hang | live demo dies | warm models at startup, `/healthz` gate, recorded fallback |
| Qdrant filter semantics differ from expectation | hits Phase 3, not 2 | prototype one filtered query in Week 3 as a throwaway spike |
| Week 1 already nearly over | checkpoint pressure | "Start here" below; mock provider counts as the Week-1 artifact |
| Makefile is Windows-venv-only | teammates blocked | route Phase 2 targets through Docker |

---

## Explicitly not in Phase 2

Verdict-filtered lookup, high-risk re-verification, cost-aware routing,
`output_guard.py`, `rate_limit.py`, Locust, ablations, the paper. Phase 2 that
tries to also be Phase 3 ends up with a defence that has no measured baseline to
beat — the baseline number *is* the deliverable.

---

## Start here — the next three commits

1. `config.py` + `schemas.py` + `providers.py` in `mock` mode + `main.py` with
   the one route → a request goes in, a canned reply comes out, no keys needed.
2. `logging_mw.py` writing the JSONL contract with the fields that exist yet →
   this is what Weeks 2–4 keep extending.
3. `Dockerfile.gateway`, compose `gateway` service, `make gateway-up` /
   `make smoke`, then flip `PROVIDER_MODE=live` once for the "the proxy works"
   screenshot.

That sequence puts a demoable Week-1 artifact in the repo without waiting on API
keys, and each step is independently committable.
