# Week 4 result: bypass rate on our own gateway

Seeds: 239.  Attack variants per threshold: 2838.  Provider: mock (no model called).

| Threshold | Lazy edits | Full rewrites | Overall |
|---|---|---|---|
| 0.95 | 90% | 2% | 68% |
| 0.90 | 95% | 13% | 75% |
| 0.85 | 97% | 28% | 80% |
| 0.80 | 98% | 44% | 85% |
| 0.75 | 99% | 62% | 90% |
| 0.70 | 99% | 74% | 93% |
| 0.65 | 100% | 86% | 96% |

Checks:

- Exact seed served the poison: 1673/1673 (must be all).
- Confirmed bypasses whose log says the filter never ran: 16637.
- Honest questions served the poison: 0/700 (must be zero).
- Safe order (screen first) bypass at 0.85: 0% (must be zero).
- Log score vs hit disagreements: 0 (must be zero).
