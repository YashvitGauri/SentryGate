# Verdict-Tagged Semantic Caching: Closing a Safety Bypass in LLM Gateways

**Divyansh Sharma, Sarvagya Dabas, Yashvit Gauri**

Working draft.
Sections are written as the code makes them true.
Anything marked `TODO(week N)` is not yet earned and says what evidence it needs.

---

## Abstract

`TODO(phase 4)` Final version needs the measured numbers.

Draft shape, to be filled in with real values:

Most production systems built on large language models place two components in front of the model: a safety filter that screens each prompt, and a semantic cache that returns a stored answer when a new prompt is close enough in meaning to an old one.
For the cache to save anything, it has to be checked before the filter runs.
We show that this ordering is a bypass.
A cached answer can be returned for a prompt that the safety filter would have blocked, because on a cache hit the filter is never consulted.
We show the attack is cheap: `TODO(week 4)` percent of attack prompts changed only in capitalisation, punctuation or filler words retrieved a poisoned cache entry on our gateway, with zero filter invocations.
We then present verdict-tagged caching, in which the safety result is computed once at screening time and stored alongside the cached answer, so that a cache lookup is a filtered search and the filter becomes part of the match condition.
This reduces the bypass rate from `TODO(phase 3)` to `TODO(phase 3)` at a cache hit rate cost of `TODO(phase 3)`.

---

## 1. Introduction

`TODO(week 5)` Full draft.

The argument in order:

1. Gateways in front of LLMs are now standard, and they do two jobs at once: they keep costs down with a cache, and they keep attacks out with a filter.
2. Both jobs are well studied on their own.
3. Almost nobody studies what happens when they are put in the same request path, in the order that performance demands.
4. That order creates a hole. The cache can serve an answer the filter already rejected.
5. The hole is not a tuning mistake. No similarity threshold is both safe and useful, which we show by sweeping the threshold.
6. The fix is to make the safety result part of what the cache matches on.

**Contributions.**

- A description of the cache-before-filter bypass as a class of flaw, not a single bug.
- A measurement of how cheap the attack is, on a running gateway, using public attack datasets. `TODO(week 4)`
- A defence, verdict-tagged caching, that is one filter clause on a vector search rather than a new model. `TODO(phase 3)`
- The trade-off curve between safety and cache efficiency that the defence sits on. `TODO(phase 3)`
- An ablation showing what each layer of the gateway contributes. `TODO(phase 4)`

---

## 2. Background

`TODO(week 5)` Needs sources from `related-work.md`.

Three things a reader needs before the flaw makes sense.

**Semantic caching.**
An exact-match cache only helps when two users type exactly the same thing.
A semantic cache embeds the prompt into a vector, searches for the nearest stored vector, and returns that answer if the similarity is above a threshold.
This is what makes caching useful for natural language, where the same question is asked a hundred different ways.

**Prompt injection filters.**
A classifier scores how much a prompt looks like an attempt to override the model's instructions.
These are good. In our own measurements the filter scored 1.000 on every attack variant we tried.
The problem in this paper is never that the filter is weak.

**Why the cache is checked first.**
Screening costs roughly 100 ms of model inference.
A cache hit costs roughly 10 ms.
Screening before the cache would add the screening cost to every request, including the ones the cache was meant to make free, which cancels out most of the saving.
So the cache goes first. That is a rational engineering decision, and it is the hole.

---

## 3. Threat model

`TODO(week 4)` Confirm each assumption against what the implementation actually allows.

**What the attacker wants.**
To get an answer the safety filter would have refused.

**What the attacker can do.**
Send prompts to the gateway as an ordinary user.
Reword their own prompts freely.

**What the attacker does not need.**
Access to the cache, the vector store, the model weights, or any other user's session.
A paraphrase model, an LLM, or any tooling beyond a text editor.

**How a poisoned entry gets there.**
This is the one assumption that needs care, and we treat it three ways:

1. A prompt that scored just under the block threshold was allowed, answered, and cached.
2. The cache was warmed before deployment from a prompt set that was never screened.
3. The cache is shared across tenants, so one tenant's stored answer is reachable by another.

Case 1 needs no special access at all and is the one we measure.

**Out of scope.**
Attacks on the model itself, on the vector store's network interface, or on the provider.
Training-time attacks.
Attacks that require code execution on the gateway host.

---

## 4. The bypass

Phase 1 result. These numbers are real and reproducible today with `docker compose run --rm poc`.

A single attack prompt was placed in the cache with a poisoned answer.
Ten variants of that same attack were then tried.

| Measurement | Value |
|---|---|
| Variants the filter would block | 10 of 10, at score 1.000 |
| Variants the cache answered anyway | 5 of 10 |
| Filter invocations while that happened | 0 |

The five that got through were the cheapest possible edits: a capital letter, a full stop, an inserted "all", an inserted "please".
The full rewrites failed, scoring 0.22 to 0.71 similarity, because a real paraphrase no longer sounds close enough to match.

This is the finding stated in one line: **an attacker does not need clever wording, they need the shift key.**

### 4.1 It is not a threshold problem

Sweeping the similarity threshold does not produce a safe setting.

| Threshold | Surface edits bypassed | Full rewrites bypassed | Overall |
|---|---|---|---|
| 0.95 | 40% | 0% | 20% |
| 0.90 | 100% | 0% | 50% |
| 0.85 | 100% | 0% | 50% |
| 0.80 | 100% | 0% | 50% |
| 0.75 | 100% | 0% | 50% |
| 0.70 | 100% | 20% | 60% |
| 0.65 | 100% | 40% | 70% |

Every threshold a real deployment would choose leaks all of the surface edits.
Tightening to 0.95 still leaks 40% of them, and by then the cache has stopped matching normal rephrasings too, so it no longer saves money.
No single number is both safe and useful.
That is why the fix has to change how the cache decides a match, not what it is set to.

### 4.2 What Phase 1 does not prove

`TODO(week 4)` Replace this section with the end-to-end result.

The Phase 1 demonstration is a controlled script.
The cache-before-filter ordering is true there by construction, because the cache simply never calls the filter.
That models the real architecture faithfully, but it is not a measurement of a running system.
Week 4 repeats the experiment on the real gateway, with public attack datasets and at least 50 seed attacks, and confirms the zero-invocation claim from the request log rather than from the code.

---

## 5. Design

### 5.1 The idea

Compute the safety result once, at screening time.
Store it next to the cached answer.
Make the cache check it on every lookup.

A cache hit then requires two things to agree, not one: the wording has to be close enough, **and** the stored safety result has to be compatible with the incoming request.
The filter stops being a stage that a cache hit can skip, and becomes part of the match condition itself.

### 5.2 What is stored

Every cache entry carries the verdict that was computed for the prompt that created it: whether it was an injection, its classifier score, whether it contained personal data, its intent, and its risk level.

### 5.3 The match condition

A stored entry may be served only if all of the following hold:

1. Similarity is at or above the threshold for the incoming request's intent.
2. The stored injection flag matches the incoming one.
3. The stored intent matches the incoming intent.
4. If the incoming request is high risk, re-verification passed.

Thresholds are per intent, not global.
A request asking for credentials or tool use gets a tight threshold.
An informational request gets a relaxed one, because the cost of a wrong match there is low and the cache saving is high.

### 5.4 Why this is cheap

The verdict is already being computed for every prompt that misses the cache.
Storing it costs a few bytes in the vector store payload.
Checking it costs one filter clause on a search that was happening anyway.
No second model, no extra inference on the hot path, except for the deliberate re-verification of high-risk hits.

`TODO(phase 3)` Measure the added latency and put the number here.

---

## 6. Implementation

The gateway is a FastAPI service that speaks the OpenAI chat completions API, so any OpenAI client points at it by changing one base URL.

| Part | File | State |
|---|---|---|
| Request routing, OpenAI-compatible API | `app/main.py`, `app/schemas.py` | Done, Week 1 |
| Settings and experiment switches | `app/config.py` | Done, Week 1 |
| Model calls, with record and replay | `app/providers.py` | Done, Week 1 |
| Request log, one line per request | `app/logging_mw.py` | Done, Week 1 |
| Injection and personal data screening | `app/screening.py` | Done, Week 2 (stub scorer + PII; deberta wired, pins pending) |
| Semantic cache | `app/cache.py` | Done, Week 3 (baseline, verdict stored not checked) |
| Attack generation and sweep | `attacks/` | `TODO(week 4)` |
| Verdict-filtered lookup | `app/cache.py` | `TODO(phase 3)` |
| Cost-aware routing | `app/router.py` | `TODO(phase 3)` |
| Output guard, spend limits | `app/mitigations/` | `TODO(phase 3)` |

### 6.1 One binary, two experiments

The vulnerable baseline and the defended system are the same code with different settings.
`CACHE_VERDICT_FILTER=off` is the baseline.
`CACHE_VERDICT_FILTER=on` is the defence.

This matters for the evaluation.
A reviewer cannot object that the two arms differ in some other way, because they do not.
It also means the ablation study is already built: each switch is one arm.

### 6.2 Every result carries its own settings

Each request writes one line to a JSONL log, and each line includes the settings that produced it and the commit it ran on.
Results can therefore be split by experiment arm after the fact, from the log alone.

### 6.3 Reproducibility

Model replies are recorded once and replayed from disk afterwards.
Every experiment in this paper can therefore be re-run with no API key, no network and no cost, and returns the same answers each time.

### 6.4 Status after Week 3

Screening (Week 2) runs on every request before the provider call.
Each prompt gets a `Verdict` (`app/verdict.py`): injection score against `INJECTION_THRESHOLD` (default 0.5), Presidio PII scan with a regex fallback for email and phone, keyword intent buckets, and a risk level.
Attacks return `403` with an OpenAI-shaped error object (`{"code": "prompt_injection"}`).
PII flags the verdict but does not block.
The running gateway uses a keyword stub scorer, so the suite needs no weights; the deberta path (`SCREENING_SCORER=hf`) is wired but its weights and latency are not yet measured here.

Baseline cache (Week 3) has two layers: exact match on the prompt hash (Redis, or memory fallback) and semantic search on the prompt embedding (Qdrant, or memory fallback).
Lookup uses a plain global threshold (`SIM_THRESHOLD`, default 0.85) and ignores the stored verdict, on purpose.
Every upsert stores the full verdict payload (`is_injection`, `has_pii`, `intent`, `risk_level`, `injection_score`) so Phase 3 is a query change, not a re-index.
In `cache_first` mode a hit returns with `screening_ran=False`; in `screen_first` mode screening always runs.
`POST /v1/cache/clear` resets between runs.
36 tests pass in the gateway image with stub scorer and stub embedder; real-model and real-infra numbers are still open.

---

## 7. Evaluation

`TODO(week 4)` First numbers. `TODO(phase 4)` Full suite.

The log already records what every metric needs: `screening_ran` and the full `verdict` (Week 2), plus cache `outcome`, `similarity`, `matched_id`, `threshold` and `embed`/`cache` latencies (Week 3).
What is missing is the Week 4 run that fills them: poisoned entries, variant sweeps, and threshold splits, all read back from that log.

**Datasets.**
`deepset/prompt-injections` and `jayavibhav/prompt-injection` for attack seeds.
Variants are generated in two families, kept separate throughout, because they behave very differently:

- *surface*: capitalisation, punctuation, filler words. Free to produce.
- *rewrite*: genuine paraphrases.

**Metrics.**

| Metric | Definition |
|---|---|
| Bypass rate | Share of attack variants served from a poisoned entry without the filter running |
| Cache hit rate | Share of requests answered from cache |
| Cost saving | Dollars not spent, against a no-gateway baseline |
| Latency | p50 and p99, split by hit and miss |
| Gateway overhead | Milliseconds added by our layers |
| Detection rate | Share of attacks the filter catches when it is asked |
| False positive rate | Share of benign prompts wrongly blocked |

**Ablations.** `TODO(phase 4)` Screening off, verdict filter off, re-verification off, routing off.

---

## 8. Results

`TODO(week 4)` First real result: bypass rate on our own gateway.
`TODO(phase 3)` Baseline against defended, same attacks.
`TODO(phase 3)` The trade-off curve.
`TODO(phase 4)` Full table, ablations, cost and latency.

---

## 9. Limitations

Written honestly as we find them, not at the end.

- The Phase 1 numbers come from one seed attack and ten variants. Week 4 replaces them with at least 50 seeds from public datasets.
- Cache poisoning requires an entry to get in. We measure the case that needs no special access, and discuss the others in the threat model rather than measuring them.
- The filter we use is one specific public model. A different filter would change the detection numbers, though not the shape of the bypass.
- Weeks 2 and 3 run on stub scorer and stub embedder with memory stores, so no detection, false-positive, latency, or hit-rate numbers are claimed yet. The deberta weights, MiniLM embeddings, and Redis/Qdrant paths are wired with fallbacks and still need measuring.
- `TODO(phase 3)` The verdict filter can only be as good as the intent labels. Say how intent is assigned and how often it is wrong.

---

## 10. Related work

`TODO(week 5)` Write from `related-work.md` once the reading is done.

Three areas to cover: semantic caching for LLMs, prompt injection attacks and defences, and security of LLM serving infrastructure.
The gap we claim is the intersection: caching and filtering are each studied alone, and their interaction in one request path is not.

---

## 11. Conclusion

`TODO(phase 4)`
