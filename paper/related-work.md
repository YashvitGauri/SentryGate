# Related work

The reading list.
Nothing gets cited in `paper.md` until it has been read and has a verified citation here.

**Status key:** `to read`, `read`, `cited`.

## Semantic caching for LLMs

| Source | Why it matters | Status |
|---|---|---|
| GPTCache, the open source semantic cache | The reference implementation of the thing we are attacking. Check what its default similarity threshold is and whether it screens at all. | to read |
| Qdrant documentation on filtered search | Payload filtering is the mechanism our defence uses. Need to confirm the filter is applied during search, not after, or the performance claim changes. | to read |
| Vendor write-ups on LLM caching in production | Evidence that cache-before-filter is what real systems do, not a straw man. This is the weakest link in our argument and needs the best sources. | to read |

## Prompt injection

| Source | Why it matters | Status |
|---|---|---|
| Perez and Ribeiro, "Ignore Previous Prompt" | The origin of the attack phrasing our seed uses. | to read |
| Greshake et al., on indirect prompt injection | Establishes that injection is a real deployed risk, not a lab curiosity. | to read |
| OWASP Top 10 for LLM Applications | Where our mitigation modules are mapped. Already used to answer the broader-coverage feedback in the Phase 1 deck. | read |
| `protectai/deberta-v3-base-prompt-injection-v2` model card | The filter we actually run. Need its reported detection and false positive rates to compare against ours. | to read |
| `deepset/prompt-injections`, `jayavibhav/prompt-injection` | Our attack seeds in Week 4. Need licence and composition. | to read |
| garak | Probe suite. Possible source of extra attack families. | to read |

## LLM serving infrastructure security

| Source | Why it matters | Status |
|---|---|---|
| Work on cache side channels in general systems | Our flaw is a cache side channel with a new payload. Older literature will have named this pattern already, and we should use their name. | to read |
| Microsoft Presidio | The personal data detector in our screening layer. | to read |

## The gap we claim

Caching is studied for cost and speed.
Filtering is studied for safety.
We have not yet found work that studies what happens when both sit in the same request path, in the order performance requires.

If that work exists, we need to find it now rather than in November.
Anyone who finds a paper that already makes this point should put it here immediately.
