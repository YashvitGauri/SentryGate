# Phase 3 result: the difficulty router

40 questions (20 easy, 20 hard, labelled by us). Live calls through OpenRouter.

| | Always strong model | Router | Saved |
|---|---|---|---|
| All questions | $0.08346 | $0.07194 | 14% |
| Easy questions | $0.00542 | $0.00041 | 92% |
| Hard questions | $0.07803 | $0.07153 | 8% |

Projected saving for other traffic mixes, from the measured average cost of each kind:

| Traffic mix | Saved |
|---|---|
| 50% easy | 14% |
| 80% easy | 27% |
| 90% easy | 41% |

Model response time, median: cheap 1898 ms, strong 2710 ms.

- Router sent 19 of 40 to the strong model.
- Router agreed with our label on 39 of 40.
- Hard questions sent to the cheap model: hard-15.
- Easy questions sent to the strong model: none.
- Requests blocked or failed: 0.
- Failover: openai/no-such-model-sentrygate failed, answered by openai/gpt-4o-mini (status 200).
