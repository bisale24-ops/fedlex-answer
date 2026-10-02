.PHONY: run airgap eval test local stop

IMAGE ?= fedlex-answer
PORT ?= 8080
LLM_BASE_URL ?= https://hackapertus.livemap.sh/v1

# Start the assistant at http://localhost:8080 (needs LLM_API_KEY for the Hack Apertus endpoint,
# or LLM_BASE_URL pointing at your own Apertus server).
run:
	docker build -q -t $(IMAGE) . >/dev/null
	docker run --rm --name $(IMAGE) -p $(PORT):8080 -e LLM_BASE_URL=$(LLM_BASE_URL) -e LLM_API_KEY -e LLM_NAME $(IMAGE)

# Air-gapped: the app and Apertus 1.5 8B on vLLM, internal network only (GPU + ./weights required).
airgap:
	docker compose --profile airgap up --build app-airgap apertus

# Re-grade the recorded evaluation on Swiss Statute QA (no network, no key) and check the published numbers.
eval:
	docker build -q -t $(IMAGE) . >/dev/null
	docker run --rm --network none $(IMAGE) python -m fa.reproduce

test:
	docker build -q -t $(IMAGE) . >/dev/null
	docker run --rm --network none $(IMAGE) python -m unittest discover -s tests -v

# Same as eval, without Docker.
local:
	PYTHONPATH=src python3 -m fa.reproduce

stop:
	-docker stop $(IMAGE)
	-docker compose --profile airgap down
