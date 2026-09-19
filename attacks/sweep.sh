#!/usr/bin/env bash
# The full Week 4 sweep. This is the Phase 2 result.
#
# For each similarity threshold, it restarts the gateway on real models (the
# threshold is fixed at startup), waits for it to be healthy, and runs the
# bypass experiment against it. Then it runs one safe-order arm, where
# screening happens before the cache, which should drop the bypass to zero and
# so proves the order is the cause.
#
# Everything runs with PROVIDER_MODE=mock: the attack only needs cache hits, so
# no model is ever called and nothing is spent.
#
# Usage:  bash attacks/sweep.sh [LIMIT]
#   LIMIT  optional, first N seeds only, for a quick check.
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT="${1:-}"
LIMIT_ARG=""
[ -n "$LIMIT" ] && LIMIT_ARG="--limit $LIMIT"

THRESHOLDS="0.95 0.90 0.85 0.80 0.75 0.70 0.65"
BUILD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
GW=http://127.0.0.1:8000

export BUILD_SHA PROVIDER_MODE=mock CACHE_VERDICT_FILTER=off CACHE_REVERIFY_HIGH_RISK=off \
       INJECTION_THRESHOLD=0.5 SCREENING_SCORER=hf CACHE_EMBEDDER=hf CACHE_BACKEND=auto \
       EMBED_MODEL=all-MiniLM-L6-v2 ALLOW_CACHE_SEED=on REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}"

echo "Week 4 sweep. Starting Qdrant and Redis."
docker compose --profile phase2 up -d qdrant redis >/dev/null

# Fresh result files. The scripts append, so old runs must not linger.
rm -f data/week4/results.jsonl data/week4/summary.jsonl data/week4/controls_results.jsonl
rm -f data/week4/run-*.jsonl

start_gateway() {  # order, threshold, logfile
    PIPELINE_ORDER="$1" SIM_THRESHOLD="$2" LOG_FILE="$3" \
        docker compose up -d --force-recreate gateway >/dev/null 2>&1
    for _ in $(seq 1 90); do
        curl -sf "$GW/healthz" >/dev/null 2>&1 && return 0
        sleep 3
    done
    echo "Gateway did not come up for threshold $2" >&2
    docker logs --tail 20 sentrygate-gateway >&2
    exit 1
}

run() {  # threshold, tag
    docker run --rm --network container:sentrygate-gateway \
        -v "$PWD":/src -w /src sentrygate-attacks \
        python attacks/run_bypass.py --threshold "$1" --tag "$2" $LIMIT_ARG
}

echo "Vulnerable order (cache_first), sweeping the threshold:"
for t in $THRESHOLDS; do
    start_gateway cache_first "$t" "week4/run-cache_first-$t.jsonl"
    run "$t" cache_first
done

echo "Safe order (screen_first) at 0.85, the control arm:"
start_gateway screen_first 0.85 "week4/run-screen_first-0.85.jsonl"
docker run --rm --network container:sentrygate-gateway -v "$PWD":/src -w /src sentrygate-attacks \
    python attacks/run_bypass.py --threshold 0.85 --tag screen_first --order screen_first $LIMIT_ARG

echo "Done. Building figures and summary table."
docker run --rm -v "$PWD":/src -w /src sentrygate-attacks python eval/make_figures.py
