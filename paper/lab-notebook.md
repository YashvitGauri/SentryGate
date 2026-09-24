# Lab notebook

One entry per week.
Written the same week, not from memory later.
Dead ends belong here too, because they are the fastest way to stop someone repeating them.

---

## Phase 2, Week 1 (23 to 29 August): the gateway skeleton

**Goal for the week.** A request goes through our own service to a model and comes back. Nothing else.

### What we built

- `app/config.py`. Every setting comes from the environment, is read once at startup, and is validated there. Bad settings fail immediately with a clear message instead of failing halfway through an experiment.
- `app/schemas.py`. The OpenAI chat completions request and reply shapes, so any OpenAI client works against us by changing one base URL.
- `app/providers.py`. Three ways of getting a reply: `mock`, `replay` and `live`.
- `app/main.py`. The `POST /v1/chat/completions` route and a `/healthz` that reports which settings the running service has.
- `app/logging_mw.py`. One JSONL line per request.
- `tests/`. 18 tests. None of them download a model or call an API.

### Decisions worth remembering

**The vulnerability is a switch, not a version.**
`PIPELINE_ORDER`, `CACHE_VERDICT_FILTER` and `CACHE_REVERIFY_HIGH_RISK` live in config.
Phase 2 runs with the filter off, which is the vulnerable baseline.
Phase 3 turns it on.
Same code, same commit, so nobody can say the two arms differ in some other way.
The Phase 4 ablation table is already built as a side effect.

**Record and replay from day one.**
A live call can be recorded to disk and replayed for free afterwards.
Three reasons: the Week 4 attack sweep fires hundreds of prompts and should not cost hundreds of prompts worth of money, the results have to be repeatable, and the live demo has to work in a room with no internet. Phase 1 taught us the last one.

**A daily spend cap, checked before every live call.**
Kept in a small file, so restarting the service does not reset it to zero.
A sweep is a loop, and a loop with a bug should cost pennies.

**Logging moved forward from Week 5.**
The plan had it late. Week 4 has to claim that the filter never ran, and the only honest evidence for that is a log line saying so.
Two fields matter most: `screening_ran`, and a `config` block on every line saying which settings produced it.

**The prompt text is never logged.**
Only a hash and a length. Caller keys are hashed too.
The prompt will live in the cache payload, where attack forensics needs it, not in a file we paste into a report.

**Routes are plain `def`, not `async def`.**
FastAPI runs a plain function in a worker thread.
The blocking classifier call in Week 2 therefore cannot stall the server, and we needed no async plumbing to get that.

### What we can show

- `/healthz` prints the running settings and the commit.
- A curl gets a proper OpenAI-shaped reply, with headers saying what happened: provider `mock`, screened `false`, cache `disabled`.
- One log line per request, complete, with the settings attached.
- `stream: true` gets a clear refusal instead of a crash, because streaming and caching interact and that has to be designed, not bolted on.

### Then we put it in Docker

- `deploy/Dockerfile.gateway`, `deploy/nginx.conf`, and `gateway` and `nginx` services in compose.
- `make gateway-up` starts both. `make gateway-smoke` proves the whole path works: nginx to gateway to a reply to a log line on the host disk.
- The commit is stamped into the image at build time, because inside a container there is no git repo to ask, and every log line has to say which build produced it.
- The image does not run as root, and it carries no models, so a code change does not rebuild the 370 MB classifier that arrives next week.
- All 18 tests pass inside the image on Python 3.11, which is the version the project actually targets.

### What went wrong

- **Docker Desktop is unreliable on the Mac used for this work.** It started, quit within a minute, and would not come back. The gateway was checked in a temporary Python 3.9 virtual environment instead. It later started on a second attempt and everything above was built and verified properly. Treat it as flaky rather than fixed: if it does this again in Week 2, that is the blocker to solve first, because Presidio and spaCy are the awkward installs and nobody wants to debug those outside a container.
- The `Makefile` pointed at a Windows virtual environment path, so it only ran on one machine. `PY` is now overridable, and every Phase 2 target goes through Docker instead.

### Honest state

There is no safety check and no cache yet.
The headers say so, and the log says so.
Nothing in the repo currently claims otherwise.

### Next week

Screening. Load the injection classifier once at startup, add the personal data scan, and produce a verdict for every request.
The measurable output is a benign prompt that passes and an attack prompt that is refused, with the score visible.

---

## Phase 2, Week 2 (30 Aug to 5 Sep): the screening layer

**Goal for the week.** Every prompt gets a `Verdict`. Attacks get a `403`.

### What we built

- `app/verdict.py`. Frozen `Verdict` shape from the spec, plus keyword intent buckets and risk rules.
- `app/screening.py`. `KeywordStubScorer` (same cues as the PoC `--fast` mode), `HuggingFaceScorer` (lazy deberta load), Presidio with regex fallback for email/phone, `Screener.screen()` folding both into a `Verdict`. `build_screener()` with `auto` / `stub` / `hf` modes so the gateway always starts.
- `app/main.py`. Screens every request before the provider call, sets `screening_ran`, `verdict`, `latency_ms.screen`, returns `403 {"code": "prompt_injection"}` on attack. Headers now say `Screened: true`, `Verdict: clean|blocked`, plus the injection score.
- `app/config.py`. New `INJECTION_THRESHOLD` (default 0.5) and `SCREENING_SCORER` (`auto|stub|hf`).
- `tests/test_screening.py`. 9 tests on the stub. Old smoke/logging tests updated to expect screened traffic. 27 pass in the gateway image on Python 3.11.

### Decisions worth remembering

- Tests never download weights. The stub is injected, and `SCREENING_SCORER=stub` keeps the lifespan fast.
- PII flags but does not block. Only `is_injection` returns 403. Blocking on PII would false-positive benign mail.
- `response_model=None` on the route, because the endpoint returns either an OpenAI body or a JSON error.

### What went wrong

- Host Python is 3.9, which cannot parse `str | None`. Verification runs inside the gateway Docker image (3.11) instead.
- FastAPI rejects `ChatCompletionResponse | JSONResponse` as a response model. Fixed with `response_model=None`.

### Honest state

- Screening is real on the stub. The deberta weights path is wired (`hf` mode) but the exact `transformers` + `torch` pins and the Presidio/spaCy install are not yet verified in Docker. That is the remaining Week 2 tail.
- No cache yet. Headers still say `Cache: disabled`.

### Next week

Cache. Redis exact + Qdrant semantic with a plain global threshold, verdict stored but not filtered. The latency drop is the demo.

---

## Phase 2, Week 3 (6 to 12 Sep): the baseline semantic cache

**Goal for the week.** Same question two ways, second one served from cache. Deliberately vulnerable.

### What we built

- `app/cache.py`. `StubEmbedder` (word-hash, no download) + `SentenceTransformerEmbedder` (lazy MiniLM), `MemoryExactStore` / `RedisExactStore`, `MemoryVectorStore` / `QdrantVectorStore`, `SemanticCache` with exact-first then threshold search. Every upsert stores the full verdict payload from the frozen contract. Lookup ignores it, on purpose.
- `app/main.py`. `cache_first` looks up before screening and serves hits with `screening_ran=False`. `screen_first` screens first, then looks up. Misses screen, call the provider, then store with the verdict. `POST /v1/cache/clear` resets between runs. Hits report `Provider: cache`, `Screened: false`, `Cache: hit`, similarity.
- `app/config.py`. New `EMBED_MODEL`, `CACHE_EMBEDDER` (`auto|stub|hf`), `CACHE_BACKEND` (`auto|memory`).
- Infra. `requirements-gateway.txt` gains `sentence-transformers`, `qdrant-client==1.13.0`, `redis`. Dockerfile installs CPU torch first. `make cache-reset` added.
- `tests/test_cache.py`. 9 tests on memory stores: stub similarity split, payload shape, miss-then-hit, reworded hit, unrelated miss, hit-skips-screening as data, clear, healthz, screen_first arm. 36 pass in the image.

### Decisions worth remembering

- Memory fallback keeps the gateway running with no Qdrant/Redis. `auto` tries the real services, falls back with a reason in `/healthz`.
- Blocked prompts are never stored. Only provider successes get cached.
- Exact match returns similarity 1.0 without embedding math.

### What went wrong

- `qdrant-client==1.12.4` does not exist on PyPI. Pinned `1.13.0`, which works against server `v1.12.4`.
- FastAPI route now returns two shapes, kept honest with `response_model=None` from Week 2.

### Honest state

- Live check on the built image: first ask `miss` with `Screened: true`, reworded ask `hit` with `Screened: false` and similarity 1.0, `POST /v1/cache/clear` returns `{"cleared": 1}`.
- Real MiniLM and real Qdrant/Redis paths are wired but not yet measured. Default run uses the stub + memory.

### Next week

Week 4, the phase result. Poison one entry, fire variants at the live gateway over HTTP, sweep thresholds, confirm `screening_ran==false` from the JSONL. That number is the slide.

---

## Phase 2, Week 4 (13 to 19 September): reproduce the bypass on our own gateway

**Goal for the week.** Stop asserting the bypass and measure it, on the real system.

### What we built

- `attacks/generate_variants.py`. Pulls two public datasets, keeps the English attacks, and makes rewordings in two families: lazy edits (fixed keyboard-level rules) and full rewrites (a local T5 paraphraser). Deterministic, so the set is reproducible. Output committed.
- `attacks/run_bypass.py`. For each attack: clear the cache, plant one poisoned entry, fire every rewording over HTTP, count a bypass only when the poison comes back AND the gateway's own log says the filter never ran.
- `attacks/sweep.sh`. Restarts the gateway on real models for each of seven thresholds, runs the experiment, then runs the safe-order control arm.
- `eval/make_figures.py`. Turns the results into the table and the chart. Nothing hand-entered.
- A test-only seed endpoint (`POST /v1/cache/seed`, off unless `ALLOW_CACHE_SEED=on`), and every log line now names the models that actually loaded.
- `make variants`, `make bypass`, `make figures`.

### The result

239 seeds, 2,838 rewordings per threshold, real filter, real MiniLM, real Qdrant and Redis.

| Threshold | Lazy | Rewrite | Overall |
|---|---|---|---|
| 0.95 | 90% | 2% | 68% |
| 0.85 | 97% | 28% | 80% |
| 0.65 | 100% | 86% | 96% |

At 0.85, a setting a real product would use, 97% of lazy rewordings were served the poison with zero filter calls.

### Checks that make it trustworthy

- Exact attack served the poison: 1673/1673.
- Honest questions served the poison: 0/700.
- Safe order (filter before cache), same attack: 0% bypass. This proves the order is the cause.
- Log similarity vs served hit: 0 disagreements.

### What went wrong

- **Docker Desktop needed a manual start again**, as in Week 1. Once up it stayed up for the whole run.
- **Redis could not bind port 6379**: a separate `shared-redis` container already held it. Made the host port configurable (`REDIS_HOST_PORT`, default now 6380). The gateway talks to Redis over the compose network, so this only affects debugging from the host.
- **HTTP headers came back lowercased**, and the first runner read them from a case-sensitive dict, so every score read as zero and nothing counted. Fixed by lowercasing header keys. Caught because the smoke test showed exact hits but zero bypasses, which was obviously wrong.
- **The gateway held a deleted log file open.** I deleted a log mid-run; the open file handle kept writing to the ghost inode, so the runner found no lines. Fixed by having the runner read the gateway's real log path from `/healthz`, and by recreating the gateway per threshold (which reopens the log).
- **The paraphraser's group-beam-search mode now needs `trust_remote_code=True`** in current transformers, which downloads and runs code from the Hub. We do not turn that on. Plain beam search is deterministic and needs no remote code, so we used that.

### Honest state

- The model reply was the fixed test reply, not a real model call. The bypass is about cache hits, so no model is needed, and this kept the run free and repeatable. A real call is still a Week 5 item.
- Personal data still uses the simple text check, not Presidio. It does not touch this result, which is about injection.

### Next week

Week 5. A first real model call, the full personal data scanner, cost and speed numbers, and the backup demo.

---

## Phase 2, Week 5 (20 to 26 September): finish the gateway

**Goal for the week.** Close Phase 2: real personal-data scanner, a live tally, speed numbers, the diagram, and a recorded demo.

### What we built

- **Presidio.** The full personal-data scanner replaces the email/phone regex. It now finds names and places too. It also loads once instead of on every request, which the old code got wrong: it rebuilt the engine per call, reloading the spaCy model every time. On real traffic that alone would have dominated the latency.
- **`/metrics/summary`.** Reads the request log and reports counts, cache hit rate, blocked attacks, and response times. This is what the demo shows on screen.
- **Latency report (`eval/latency_report.py`, `make eval`).** Reads the request logs and reports p50/p99 for hits, misses and blocks. From 25,416 real requests: hit 14 ms, miss 94 ms, blocked 84 ms.
- **`docs/architecture-current.mmd`.** A diagram of what actually runs today, with the cache checked before the filter and the not-yet-wired parts greyed out.
- **`attacks/demo.py`, `make gateway-demo`.** A short end-to-end walk-through, recorded to `docs/captures/gateway-week5.txt` as the on-stage fallback.

### The number that matters

A cache hit answers in 14 ms. A miss pays the safety check and takes 94 ms, about seven times slower. That gap is the whole reason the cache goes first, and so the whole reason the bypass exists. It also says why the fix cannot be "just screen everything": that throws the speed-up away.

### What went wrong

- **Redis would not resolve from the gateway** after a plain `docker compose up gateway`: the Redis container was not running, so the gateway fell back to an in-memory store. Started Redis explicitly and recreated the gateway. `/healthz` names the backend, so this was caught immediately rather than silently running on memory.
- **`make eval` failed with `No module named app`.** The latency script imports `app.metrics`, but run as a plain script the repo root was not on the path. Fixed by running it as a module (`python -m eval.latency_report`).
- **One PII test broke once Presidio was installed.** It assumed the regex fallback and expected "France" not to be flagged, but Presidio correctly flags it as a place. Split into two tests: the regex fallback tested directly, and Presidio tested for the clear email case.

### Honest state

- Phase 2 is complete. 54 tests pass.
- One item is carried into Phase 3: a first real model reply. The two tries on 9 September failed at the provider, which is an account problem. Phase 3 Week 1 calls a model on every cache miss, so it lands there on a working account. Nothing in Phase 2 needed it, because the bypass is about answers served from the cache.

### Next

Phase 3, Week 1. Turn on the verdict check in the cache and rerun the exact Week 4 attacks. The bypass rate should drop sharply. That is the first proof the fix works.
