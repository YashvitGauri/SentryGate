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
