#!/usr/bin/env bash
# Phase 3: the router and failover, on real paid calls through OpenRouter.
#
#   1. router arm   ROUTER_MODE=difficulty, 40 questions
#   2. strong arm   every question to the strong model, same 40 questions
#   3. failover     the cheap model is set to a name that does not exist,
#                   so the call fails and the fallback model answers
#
# Needs OPENAI_API_KEY and OPENAI_BASE_URL in .env (never printed). Costs
# about $0.20; the gateway's daily spend cap still applies. Answers are saved
# as recordings, so the run can be replayed later for free.
#
# Usage:  bash attacks/router_live.sh [LIMIT]
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT="${1:-}"
LIMIT_ARG=""
[ -n "$LIMIT" ] && LIMIT_ARG="--limit $LIMIT"
GW=http://127.0.0.1:8000
CHEAP=openai/gpt-4o-mini
STRONG=openai/gpt-4o
export BUILD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
       PROVIDER_MODE=live PROVIDER_RECORD=on PIPELINE_ORDER=cache_first SIM_THRESHOLD=0.85 \
       SCREENING_SCORER=hf CACHE_EMBEDDER=hf CACHE_BACKEND=auto HF_HUB_OFFLINE=1 \
       CACHE_VERDICT_FILTER=on CACHE_REVERIFY_HIGH_RISK=on REVERIFY_SCOPE=all \
       ROUTER_CHEAP_MODEL="$CHEAP" ROUTER_STRONG_MODEL="$STRONG" DEFAULT_MODEL="$CHEAP" \
       REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}"

docker compose --profile phase2 up -d qdrant redis >/dev/null
mkdir -p data/router
rm -f data/router/results.jsonl data/router/failover.jsonl

start_gateway() {  # router mode, fallback model, logfile
    ROUTER_MODE="$1" FALLBACK_MODEL="$2" LOG_FILE="$3" \
        docker compose up -d --force-recreate gateway >/dev/null 2>&1
    for _ in $(seq 1 90); do
        curl -sf "$GW/healthz" >/dev/null 2>&1 && return 0
        sleep 3
    done
    echo "Gateway did not come up" >&2; docker logs --tail 20 sentrygate-gateway >&2; exit 1
}
in_attacks() {
    docker run --rm --network container:sentrygate-gateway -v "$PWD":/src -w /src sentrygate-attacks "$@"
}

echo "Router arm:"
start_gateway difficulty "" router/run-router.jsonl
in_attacks python attacks/run_router.py --arm router --model "$CHEAP" --expect router=difficulty $LIMIT_ARG

echo "Always-strong arm:"
start_gateway fixed "" router/run-strong.jsonl
in_attacks python attacks/run_router.py --arm strong --model "$STRONG" --expect router=fixed $LIMIT_ARG

echo "Failover: the cheap model name is broken on purpose, the fallback should answer."
ROUTER_CHEAP_MODEL=openai/no-such-model-sentrygate start_gateway difficulty "$CHEAP" router/run-failover.jsonl
curl -s -D - -o /dev/null "$GW/v1/cache/clear" -X POST >/dev/null
curl -s -D data/router/failover-headers.txt -o data/router/failover-body.json "$GW/v1/chat/completions" \
    -H 'content-type: application/json' \
    -d '{"model":"'"$CHEAP"'","messages":[{"role":"user","content":"What is the capital of Japan?"}],"max_tokens":20}'
grep -i "^x-sentrygate" data/router/failover-headers.txt | grep -iv "request-id"
tail -1 data/router/run-failover.jsonl > data/router/failover.jsonl

echo "Done. Building the router report."
in_attacks python -m eval.router_report
