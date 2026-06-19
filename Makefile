SHELL := /bin/bash

SERVER_DIR := backend/server
AGENT_DIR  := backend/voice-agent
CLIENT_DIR := client

.PHONY: help install install-server install-agent install-client \
        server agent agent-console client \
        start start-all test

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## --- setup ---------------------------------------------------------------

install: install-server install-agent install-client ## Install all dependencies

install-server: ## Sync server (FastAPI) deps
	cd $(SERVER_DIR) && uv sync

install-agent: ## Sync voice-agent deps + download model files
	cd $(AGENT_DIR) && uv sync && uv run python -m livekit.agents download-files

install-client: ## Install client (React) deps
	cd $(CLIENT_DIR) && npm install

## --- run individually ----------------------------------------------------

server: ## Run the FastAPI admin server (http://localhost:8000)
	cd $(SERVER_DIR) && uv run server

agent: ## Run the voice-agent worker (dev mode, connects to LiveKit)
	cd $(AGENT_DIR) && uv run voice-agent dev

agent-console: ## Run the voice-agent locally in console mode (mic/speaker)
	cd $(AGENT_DIR) && uv run voice-agent console

client: ## Run the React client dev server (http://localhost:5173)
	cd $(CLIENT_DIR) && npm run dev

## --- run together --------------------------------------------------------

start: ## Start the server + voice-agent together (Ctrl-C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) -s server & \
	$(MAKE) -s agent & \
	wait

start-all: ## Start the server + voice-agent + client together
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) -s server & \
	$(MAKE) -s agent & \
	$(MAKE) -s client & \
	wait

## --- tests ---------------------------------------------------------------

test: ## Run server + voice-agent test suites
	cd $(SERVER_DIR) && uv run pytest -q
	cd $(AGENT_DIR) && uv run pytest -q
