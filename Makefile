# Host python, only used by the Phase 1 targets. Override on any machine
# where the venv lives somewhere else:  make demo PY=python3.11
PY ?= ./.venv/Scripts/python.exe

# Stamped into the image so the running service reports its own commit.
BUILD_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
GATEWAY := http://127.0.0.1:8080

.PHONY: docker-build docker-demo docker-demo-run docker-demo-fast phase2-up phase2-down demo demo-fast poc poc-fast capture diagram deck present freeze \
        gateway-build gateway-up gateway-down gateway-logs gateway-smoke gateway-test cache-reset

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

gateway-test:   ## Run the test suite inside the image
	docker run --rm -v $(CURDIR):/src -w /src sentrygate-gateway python -m pytest -q

cache-reset:    ## Clean the cache between experiments (never by hand)
	@curl -fsS -X POST $(GATEWAY)/v1/cache/clear | python3 -m json.tool


MMD = problem flow architecture

diagram:        ## every mermaid source -> png, light for print + dark for the deck
	@for d in $(MMD); do 	  npx -y @mermaid-js/mermaid-cli -i docs/$$d.mmd -o docs/$$d.png -b white -w 1800; 	  npx -y @mermaid-js/mermaid-cli -i docs/$$d.mmd -o docs/captures/$$d-dark.png -t dark -b transparent -w 2000 -s 2; 	done

deck:           ## Rebuild docs/deck.html from the template + the captured run
	$(PY) docs/build_deck.py

present:        ## Serve the deck at http://127.0.0.1:8777/deck.html
	@echo "Open http://127.0.0.1:8777/deck.html  (Ctrl-C to stop)"
	cd docs && $(CURDIR)/.venv/Scripts/python.exe -m http.server 8777 --bind 127.0.0.1

freeze:
	$(PY) -m pip freeze > requirements-lock.txt
