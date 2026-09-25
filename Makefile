# Host python, only used by the Phase 1 targets. Override on any machine
# where the venv lives somewhere else:  make demo PY=python3.11
PY ?= ./.venv/Scripts/python.exe

# Stamped into the image so the running service reports its own commit.
BUILD_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
GATEWAY := http://127.0.0.1:8080

.PHONY: docker-build docker-demo docker-demo-run docker-demo-fast phase2-up phase2-down demo demo-fast poc poc-fast capture diagram deck present freeze \
        gateway-build gateway-up gateway-down gateway-logs gateway-smoke gateway-test gateway-demo paper-pdf variants bypass figures eval deck-phase2 deck-phase2-pptx report report-pptx cache-reset live-smoke

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

gateway-down:
	docker compose down

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

gateway-demo:   ## Record the full end-to-end demo to docs/captures/ (gateway must be up with ALLOW_CACHE_SEED=on)
	docker run --rm --network container:sentrygate-gateway -v $(CURDIR):/src -w /src sentrygate-attacks python attacks/demo.py | tee docs/captures/gateway-week5.txt

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

figures: attacks-build  ## Rebuild the table and chart from the results
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.make_figures

eval: attacks-build     ## Regenerate every figure from the logs (bypass + latency)
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.make_figures
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-attacks python -m eval.latency_report


MMD = problem flow architecture architecture-current

diagram:        ## every mermaid source -> png, light for print + dark for the deck
	@for d in $(MMD); do 	  npx -y @mermaid-js/mermaid-cli@11 -i docs/$$d.mmd -o docs/$$d.png -b white -w 1800; 	  npx -y @mermaid-js/mermaid-cli@11 -i docs/$$d.mmd -o docs/captures/$$d-dark.png -t dark -b transparent -w 2000 -s 2; 	done

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

report-pptx:    ## Build the Progress Report 2 deck (reports/out/SentryGate_Progress_Report_2.pptx + .pdf)
	@node -e "require('pptxgenjs')" 2>/dev/null || npm install --no-save pptxgenjs
	node reports/build_progress2_pptx.js
	@docker image inspect sentrygate-office >/dev/null 2>&1 || docker build -q -f deploy/Dockerfile.office -t sentrygate-office .
	docker run --rm -v $(CURDIR)/reports/out:/work sentrygate-office SentryGate_Progress_Report_2.pptx

present:        ## Serve the deck at http://127.0.0.1:8777/deck.html
	@echo "Open http://127.0.0.1:8777/deck.html  (Ctrl-C to stop)"
	cd docs && $(CURDIR)/.venv/Scripts/python.exe -m http.server 8777 --bind 127.0.0.1

freeze:
	$(PY) -m pip freeze > requirements-lock.txt

live-smoke:     ## One real call through the gateway (needs env key, never stored)
	@test -n "$$OPENAI_API_KEY" || (echo 'Set OPENAI_API_KEY first. Never commit it.' && exit 1)
	BUILD_SHA=$(BUILD_SHA) PROVIDER_MODE=live OPENAI_API_KEY="$$OPENAI_API_KEY" OPENAI_BASE_URL="$${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}" DEFAULT_MODEL="$${LIVE_MODEL:-openai/gpt-4o-mini}" docker compose up -d --build gateway nginx
	@sleep 6
	@curl -fsS -D /tmp/sg-live-headers.txt $(GATEWAY)/v1/chat/completions -H 'content-type: application/json' -d '{"model":"'"$${LIVE_MODEL:-openai/gpt-4o-mini}"'","messages":[{"role":"user","content":"Reply with OK only"}],"max_tokens":5}' | python3 -m json.tool
	@grep -i x-sentrygate /tmp/sg-live-headers.txt
