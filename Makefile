SHELL := /bin/bash

SERVER_DIR := backend/server
AGENT_DIR  := backend/voice-agent
CLIENT_DIR := client

SERVER_PORT := 8000
CLIENT_PORT := 5173

.PHONY: help kill-port kill-server kill-client \
        install install-server install-agent install-client \
        server agent agent-console client \
        start start-all test

kill-port: ## Kill processes listening on a given port (usage: make kill-port PORT=8000)
	@pid=$$(lsof -ti :$(PORT) 2>/dev/null); \
	if [ -n "$$pid" ]; then \
		echo "killing process(es) on port $(PORT): $$pid"; \
		kill $$pid 2>/dev/null; \
		sleep 0.5; \
		if kill -0 $$pid 2>/dev/null; then \
			kill -9 $$pid 2>/dev/null; \
		fi; \
	fi

kill-server: ## Kill any process on the server port ($(SERVER_PORT))
	$(MAKE) kill-port PORT=$(SERVER_PORT)

kill-client: ## Kill any process on the client port ($(CLIENT_PORT))
	$(MAKE) kill-port PORT=$(CLIENT_PORT)

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

server: kill-server ## Run the FastAPI admin server (http://localhost:$(SERVER_PORT))
	cd $(SERVER_DIR) && uv run server

agent: ## Run the voice-agent worker (dev mode, connects to LiveKit)
	cd $(AGENT_DIR) && uv run voice-agent dev

agent-console: ## Run the voice-agent locally in console mode (mic/speaker)
	cd $(AGENT_DIR) && uv run voice-agent console

client: kill-client ## Run the React client dev server (http://localhost:$(CLIENT_PORT))
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
