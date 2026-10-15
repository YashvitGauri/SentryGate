# Phase 3 result: the defence against cache poisoning

Threshold 0.85 (0.95 for risky kinds of question).  Seeds: 239.  Honest questions: 99.  Provider: mock (no model called).

Poison labelled clean = an attack that slipped past the filter once (the realistic case).
Poison labelled attack = the filter flagged it when it was saved (the easy case).

The filter on its own blocks 60.2% of these rewordings.
Cache-caused = poison served on a text the filter would have blocked. Only this part is the cache's fault.

| Arm | Labelled clean: served | of which cache-caused | Labelled attack: served | of which cache-caused | Honest hit rate | Honest hits re-checked | Hit p50 | Miss p50 |
|---|---|---|---|---|---|---|---|---|
| No defence | 79.9% | 49.8% | 79.9% | 49.8% | 95.0% | 0% | 17.7 ms | 153.2 ms |
| Label match only | 76.6% | 47.0% | 30.0% | 1.5% | 95.0% | 0% | 8.3 ms | 121.8 ms |
| Re-check risky hits only | 62.6% | 32.6% | 31.4% | 1.3% | 95.0% | 0% | 7.3 ms | 99.8 ms |
| Label match + re-check risky hits | 61.3% | 31.7% | 29.8% | 1.3% | 95.0% | 0% | 10.1 ms | 108.2 ms |
| Label match + re-check every hit | 29.6% | 0.0% | 28.5% | 0.0% | 95.0% | 100% | 106.7 ms | 118.8 ms |

Checks:

- No defence: honest questions served the poison: 0 (must be zero).
- Label match only: honest questions served the poison: 0 (must be zero).
- Re-check risky hits only: honest questions served the poison: 0 (must be zero).
- Label match + re-check risky hits: honest questions served the poison: 0 (must be zero).
- Label match + re-check every hit: honest questions served the poison: 0 (must be zero).
