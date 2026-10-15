#!/usr/bin/env bash
# The Phase 3 sweep: does the defence stop the attack, and what does it cost?
#
# Five arms, all at threshold 0.85 with the vulnerable cache_first order:
#
#   base      no defence                       (the Phase 2 result again)
#   filter    verdict-tagged lookup only
#   recheck   selective re-check only (risky-looking hits)
#   both      verdict-tagged lookup + selective re-check
#   all       verdict-tagged lookup + re-check of every hit (the safe setting)
#
# Each arm runs three experiments:
#   attack    poison planted labelled "attack" (the easy case)
#   clean     poison planted labelled "clean"  (the realistic case: it slipped past once)
#   benign    honest questions reworded, to count cache hits the defence loses
#
# Real models, PROVIDER_MODE=mock (no money spent), HF_HUB_OFFLINE=1.
#
# Usage:  bash attacks/sweep_phase3.sh [LIMIT]
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT="${1:-}"
LIMIT_ARG=""
[ -n "$LIMIT" ] && LIMIT_ARG="--limit $LIMIT"
OUT=data/phase3
GW=http://127.0.0.1:8000
BUILD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

export BUILD_SHA PROVIDER_MODE=mock PROVIDER_RECORD=off PIPELINE_ORDER=cache_first SIM_THRESHOLD=0.85 \
       CACHE_STRICT_THRESHOLD=0.95 REVERIFY_SCORE=0.2 INJECTION_THRESHOLD=0.5 \
       SCREENING_SCORER=hf CACHE_EMBEDDER=hf CACHE_BACKEND=auto EMBED_MODEL=all-MiniLM-L6-v2 \
       ALLOW_CACHE_SEED=on HF_HUB_OFFLINE=1 REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}"

echo "Phase 3 sweep. Starting Qdrant and Redis."
docker compose --profile phase2 up -d qdrant redis >/dev/null
mkdir -p "$OUT"
# Fresh result files. The scripts append, so old runs must not linger.
rm -f data/phase3/*.jsonl

start_gateway() {  # verdict_filter, reverify, scope, logfile
    CACHE_VERDICT_FILTER="$1" CACHE_REVERIFY_HIGH_RISK="$2" REVERIFY_SCOPE="$3" LOG_FILE="$4" \
        docker compose up -d --force-recreate gateway >/dev/null 2>&1
    for _ in $(seq 1 90); do
        curl -sf "$GW/healthz" >/dev/null 2>&1 && return 0
        sleep 3
    done
    echo "Gateway did not come up for arm filter=$1 reverify=$2" >&2
    docker logs --tail 20 sentrygate-gateway >&2
    exit 1
}

in_attacks() {
    docker run --rm --network container:sentrygate-gateway -v "$PWD":/src -w /src sentrygate-attacks "$@"
}

for arm in "base off off risky" "filter on off risky" "recheck off on risky" "both on on risky" "all on on all"; do
    set -- $arm
    tag=$1; vf=$2; rv=$3; scope=$4
    echo "Arm $tag (verdict_filter=$vf, reverify=$rv, scope=$scope):"
    start_gateway "$vf" "$rv" "$scope" "phase3/run-$tag.jsonl"
    for label in clean attack; do
        in_attacks python attacks/run_bypass.py --threshold 0.85 --tag "$tag" --out "$OUT" \
            --poison-label "$label" --expect verdict_filter="$vf" --expect reverify="$rv" \
            --expect reverify_scope="$scope" $LIMIT_ARG
    done
    in_attacks python attacks/run_benign.py --threshold 0.85 --tag "$tag" --out "$OUT" \
        --expect verdict_filter="$vf" --expect reverify="$rv" --expect reverify_scope="$scope" $LIMIT_ARG
done

echo "Done. Building Phase 3 figures."
in_attacks python -m eval.phase3_figures
