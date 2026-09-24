# Gateway latency, from the request logs

Measured on the Week 4 traffic. Provider was mock, so a miss's model time is the mock reply, not a real model.

| Outcome | Requests | p50 (ms) | p99 (ms) |
|---|---|---|---|
| Cache hit | 20076 | 13.7 | 108.4 |
| Miss (screen + model) | 1830 | 94.4 | 265.4 |
| Blocked attack | 3510 | 83.7 | 236.3 |

A cache hit answers in about 14 ms at the median.
A miss pays the safety check on top, at about 94 ms.
That gap is exactly why real systems check the cache first, and why the bypass exists.
