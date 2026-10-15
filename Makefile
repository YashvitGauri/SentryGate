# Host python, only used by the Phase 1 targets. Override on any machine
# where the venv lives somewhere else:  make demo PY=python3.11
PY ?= ./.venv/Scripts/python.exe

# Stamped into the image so the running service reports its own commit.
BUILD_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
GATEWAY := http://127.0.0.1:8080
# 6379 is often taken by another local Redis; the gateway reaches Redis
# over the compose network, so the host port only matters for debugging.
REDIS_HOST_PORT ?= 6380
export REDIS_HOST_PORT

.PHONY: docker-build docker-demo docker-demo-run docker-demo-fast phase2-up phase2-down demo demo-fast poc poc-fast capture diagram deck present freeze \
        gateway-build gateway-up gateway-down gateway-logs gateway-smoke gateway-test demo-up gateway-demo paper-pdf variants bypass figures eval deck-phase2 deck-phase2-pptx report report-pptx cache-reset live-smoke defence defence-figures lint report3 report3-pptx

docker-build:   ## Build the image (bakes both models in, ~2.2GB, takes a few min)
	docker compose build poc

docker-demo:    ## PREFERRED live demo: steps through on Enter, no network
	docker compose run --rm poc --pause

docker-demo-run: ## Same but runs straight through without pausing
	docker compose run --rm poc

docker-demo-fast: ## Same but keyword stand-in, ~3s
	docker compose run --rm poc --fast

phase2-up:      ## Start Qdrant + Redis (Phase 2 infrastructure)
	docker compose --profile phase2 up -d qdrant redis

phase2-down:
	docker compose --profile phase2 down

demo:           ## Host-Python demo (needs the venv): real deberta filter, fully offline, no noise
	HF_HUB_OFFLINE=1 $(PY) poc_bypass.py

demo-fast:      ## Fallback if anything is wrong with the model cache (~5s)
	HF_HUB_OFFLINE=1 $(PY) poc_bypass.py --fast

poc:            ## Same as demo but allowed to reach the network (first run)
	$(PY) poc_bypass.py

poc-fast:
	$(PY) poc_bypass.py --fast

capture:        ## Re-record the run the deck quotes from
	HF_HUB_OFFLINE=1 $(PY) poc_bypass.py > docs/captures/demo-output.txt 2>&1
	sed -i 's/\r$$//' docs/captures/demo-output.txt

# --- Phase 2 gateway --------------------------------------------------------
# All of these go through Docker, so they work on every machine. Nothing here
# needs an API key: the gateway starts in mock mode.

gateway-build:  ## Build the gateway image
	BUILD_SHA=$(BUILD_SHA) docker compose build gateway

gateway-up:     ## Start nginx + gateway on http://127.0.0.1:8080
	BUILD_SHA=$(BUILD_SHA) docker compose up -d --build gateway nginx
	@echo "gateway is on $(GATEWAY)  (try: make gateway-smoke)"

gateway-down:   ## Stop everything: nginx, gateway, Qdrant and Redis
	docker compose --profile phase2 down

gateway-logs:
	docker compose logs -f gateway

gateway-smoke:  ## Prove it works: health, a real request, and the log line
	@echo "--- health ---"
	@curl -fsS $(GATEWAY)/healthz | python3 -m json.tool
	@echo "\n--- a request ---"
	@curl -fsS -D /tmp/sg-headers.txt $(GATEWAY)/v1/chat/completions \
	  -H 'content-type: application/json' \
	  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"what is the capital of France?"}]}' \
	  | python3 -m json.tool
	@echo "\n--- what happened to it ---"
	@grep -i x-sentrygate /tmp/sg-headers.txt
	@echo "\n--- the log line ---"
	@tail -1 data/requests.jsonl | python3 -m json.tool

demo-up:        ## Start the gateway for the live demo: real models, seeding on, free mock replies, offline
	@rm -f data/demo/requests.jsonl   # fresh log, so the demo's tally counts only this session
	docker compose --profile phase2 up -d qdrant redis
	BUILD_SHA=$(BUILD_SHA) PROVIDER_MODE=mock PROVIDER_RECORD=off PIPELINE_ORDER=cache_first \
	  CACHE_VERDICT_FILTER=off SIM_THRESHOLD=0.85 SCREENING_SCORER=hf CACHE_EMBEDDER=hf \
	  CACHE_BACKEND=auto ALLOW_CACHE_SEED=on LOG_FILE=demo/requests.jsonl HF_HUB_OFFLINE=1 \
	  docker compose up -d --force-recreate gateway nginx
	@echo "loading models (about a minute)..."
	@for i in $$(seq 1 60); do curl -sf $(GATEWAY)/healthz >/dev/null 2>&1 && break; sleep 3; done
	@curl -fsS $(GATEWAY)/healthz | python3 -c "import json,sys; d=json.load(sys.stdin); c=d['config']; print('ready:', c['scorer'].split('/')[-1], '|', c['embedder'], '|', c['cache_backend'], '| seeding', 'on' if d['cache_seed_enabled'] else 'OFF')"

gateway-demo:   ## Run the live end-to-end demo (start it with make demo-up). Output also saved to data/demo/last-demo.txt
	@mkdir -p data/demo
	docker run --rm --network container:sentrygate-gateway -v $(CURDIR):/src -w /src sentrygate-attacks python attacks/demo.py | tee data/demo/last-demo.txt

gateway-test:   ## Run the test suite inside the image
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-gateway python -m pytest -q

cache-reset:    ## Clean the cache between experiments (never by hand)
	@curl -fsS -X POST $(GATEWAY)/v1/cache/clear | python3 -m json.tool


paper-pdf:      ## Build paper/SentryGate-paper.pdf from paper/paper.md (needs Chrome + pip install markdown)
	python3 paper/build_pdf.py

# --- Phase 2 Week 4: reproduce the bypass -----------------------------------
attacks-build:  ## Build the attack-tools image (datasets + charts, on the gateway image)
	BUILD_SHA=$(BUILD_SHA) docker compose build gateway
	docker build -q -f deploy/Dockerfile.attacks -t sentrygate-attacks .

variants: attacks-build  ## Regenerate the attack variants from public datasets
	docker run --rm -v $(CURDIR):/src -v sentrygate_hf_models:/models -e HF_HOME=/models sentrygate-attacks python attacks/generate_variants.py

bypass: attacks-build   ## Run the full sweep on the real gateway (the Phase 2 result)
	bash attacks/sweep.sh

lint:           ## Check the Python code with ruff (pinned, in a throwaway container)
	docker run --rm -v $(CURDIR):/src -w /src python:3.11-slim sh -c \
	  "pip install -q ruff==0.6.9 && ruff check --select E,F,W --line-length 120 app attacks eval tests reports"

defence: attacks-build  ## Run the Phase 3 sweep: five defence arms, both poison labels, honest questions
	bash attacks/sweep_phase3.sh

defence-figures: attacks-build  ## Rebuild the Phase 3 table and charts from the results
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.phase3_figures

figures: attacks-build  ## Rebuild the table and chart from the results
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.make_figures

eval: attacks-build     ## Regenerate every figure from the logs (bypass + latency)
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.make_figures
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.latency_report


MMD = problem flow architecture architecture-current architecture-phase3

diagram:        ## every mermaid source -> png, light for print + dark for the deck
	@for d in $(MMD); do 	  npx -y @mermaid-js/mermaid-cli@11 -i docs/$$d.mmd -o docs/$$d.png -b white -w 1800; 	  npx -y @mermaid-js/mermaid-cli@11 -i docs/$$d.mmd -o docs/captures/$$d-dark.png -t dark -b transparent -w 2000 -s 2; 	done
	@# the report is portrait: the same Phase 3 diagram, drawn top to bottom
	sed 's/^flowchart LR$$/flowchart TB/' docs/architecture-phase3.mmd > reports/assets/.architecture-phase3-tb.mmd
	npx -y @mermaid-js/mermaid-cli@11 -i reports/assets/.architecture-phase3-tb.mmd -o reports/assets/architecture-phase3.png -b white -w 1400
	rm -f reports/assets/.architecture-phase3-tb.mmd

deck:           ## Rebuild docs/deck.html from the template + the captured run
	$(PY) docs/build_deck.py

deck-phase2:    ## Rebuild docs/deck-phase2.html from the Week 4/5 results
	python3 docs/build_deck_phase2.py

deck-phase2-pptx: ## Rebuild the editable PowerPoint (docs/deck-phase2.pptx)
	@node -e "require('pptxgenjs')" 2>/dev/null || npm install --no-save pptxgenjs
	node docs/build_deck_phase2_pptx.js

report:         ## Build Progress Report-2 (reports/out/Progress2.docx + .pdf) in the college format
	python3 reports/build_progress2.py
	@docker image inspect sentrygate-office >/dev/null 2>&1 || docker build -q -f deploy/Dockerfile.office -t sentrygate-office .
	docker run --rm -v $(CURDIR)/reports/out:/work sentrygate-office Progress2.docx
	@echo "wrote reports/out/Progress2.pdf"

report3:        ## Build Progress Report-3 (reports/out/Progress3.docx + .pdf) in the college format
	python3 reports/build_progress3.py
	@docker image inspect sentrygate-office >/dev/null 2>&1 || docker build -q -f deploy/Dockerfile.office -t sentrygate-office .
	docker run --rm -v $(CURDIR)/reports/out:/work sentrygate-office Progress3.docx
	@echo "wrote reports/out/Progress3.pdf"

report-pptx:    ## Build the Progress Report 2 deck (reports/out/SentryGate_Progress_Report_2.pptx + .pdf)
	@node -e "require('pptxgenjs')" 2>/dev/null || npm install --no-save pptxgenjs
	node reports/build_progress2_pptx.js
	@docker image inspect sentrygate-office >/dev/null 2>&1 || docker build -q -f deploy/Dockerfile.office -t sentrygate-office .
	docker run --rm -v $(CURDIR)/reports/out:/work sentrygate-office SentryGate_Progress_Report_2.pptx

report3-pptx:   ## Build the Progress Report 3 deck for the 24 Oct review (reports/out/SentryGate_Progress_Report_3.pptx + .pdf)
	@node -e "require('pptxgenjs')" 2>/dev/null || npm install --no-save pptxgenjs@3.12.0
	node reports/build_progress3_pptx.js
	@docker image inspect sentrygate-office >/dev/null 2>&1 || docker build -q -f deploy/Dockerfile.office -t sentrygate-office .
	docker run --rm -v $(CURDIR)/reports/out:/work sentrygate-office SentryGate_Progress_Report_3.pptx

present:        ## Serve the decks at http://127.0.0.1:8777 (Phase 1: deck.html, Phase 2: deck-phase2.html)
	@echo "Phase 1 deck: http://127.0.0.1:8777/deck.html"
	@echo "Phase 2 deck: http://127.0.0.1:8777/deck-phase2.html   (Ctrl-C to stop)"
	cd docs && python3 -m http.server 8777 --bind 127.0.0.1

freeze:
	$(PY) -m pip freeze > requirements-lock.txt

live-smoke:     ## One real call through the gateway (needs env key, never stored)
	@test -n "$$OPENAI_API_KEY" || (echo 'Set OPENAI_API_KEY first. Never commit it.' && exit 1)
	BUILD_SHA=$(BUILD_SHA) PROVIDER_MODE=live OPENAI_API_KEY="$$OPENAI_API_KEY" OPENAI_BASE_URL="$${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}" DEFAULT_MODEL="$${LIVE_MODEL:-openai/gpt-4o-mini}" docker compose up -d --build gateway nginx
	@sleep 6
	@curl -fsS -D /tmp/sg-live-headers.txt $(GATEWAY)/v1/chat/completions -H 'content-type: application/json' -d '{"model":"'"$${LIVE_MODEL:-openai/gpt-4o-mini}"'","messages":[{"role":"user","content":"Reply with OK only"}],"max_tokens":5}' | python3 -m json.tool
	@grep -i x-sentrygate /tmp/sg-live-headers.txt
