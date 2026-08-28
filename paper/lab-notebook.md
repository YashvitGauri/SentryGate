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

### What went wrong

- **Docker Desktop would not stay running** on the Mac used for this work. It starts and quits within a minute. Worked around by testing in a temporary Python 3.9 virtual environment. That is fine as a check, but the project targets Python 3.11 and Docker has to work before the gateway image is built. This is the top blocker for Week 2, because Presidio and spaCy are the awkward installs and we do not want to debug them outside a container.
- The `Makefile` still points at a Windows virtual environment path, which means it only runs on one team member's machine. Phase 2 targets should go through Docker.

### Honest state

There is no safety check and no cache yet.
The headers say so, and the log says so.
Nothing in the repo currently claims otherwise.

### Next week

Screening. Load the injection classifier once at startup, add the personal data scan, and produce a verdict for every request.
The measurable output is a benign prompt that passes and an attack prompt that is refused, with the score visible.
