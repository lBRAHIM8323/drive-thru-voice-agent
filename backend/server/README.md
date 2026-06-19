# Drive-Thru Admin API (`backend/server`)

FastAPI service the admin frontend uses to manage the menu and the configuration
the voice-agent consumes. Storage is **PostgreSQL** via SQLModel.

## Run

```bash
cp .env.example .env   # set POSTGRES_* + provider keys you need
uv sync
uv run server          # http://localhost:8000  (docs at /docs)
# or: uv run uvicorn server.app:app --reload
```

On startup the app runs a lightweight migration: it creates the database if it's
missing, creates any missing tables (idempotent `create_all`), and seeds a
default branch, the singleton parser config, and — if `ADMIN_USERNAME` /
`ADMIN_PASSWORD` are set — an admin user.

## Schema

`users`, `branches`, `menu_items` + `menu_item_sizes`, `documents`,
`agent_configs`, `parser_config`, `sessions`, `orders` + `order_items`.
Money is `Numeric(12,2)`; enum-like fields are validated at the schema layer.

## API (`/api/v1`)

- **Branches** — `GET/POST /branches`, `GET/PATCH/DELETE /branches/{id}`
- **Menu** — `GET/POST /menu`, `GET/PATCH/DELETE /menu/{id}` (per-size pricing)
- **Documents (upload + parse)** — `POST /documents` (multipart `file` or `text`
  form field; accepts text/markdown, PDF, image, CSV), `GET /documents`,
  `GET/PATCH/DELETE /documents/{id}`,
  `POST /documents/{id}/confirm?mode=merge|replace` (commit parsed items to menu)
- **Agent configs** — `GET/POST /agent-configs`, `GET/PATCH/DELETE /agent-configs/{id}`.
  `GET /agent-configs/{id}` returns the bare `AgentConfig` the voice-agent fetches.
- **Parser config** — `GET/PUT /parser-config` (which LLM parses uploaded menus)

## Notes

- CSV is parsed deterministically; other formats go through the admin-selected
  LLM provider (OpenAI / Anthropic / Google). Provider keys come from the
  environment, never from requests.
- `schemas/agent_config.py` mirrors `voice-agent`'s `config.py` — keep them in
  sync (the JSON shape is the contract between the two projects).
- `sessions` / `orders` / `users` tables exist but have no routers yet (populated
  by the agent integration and auth work later).
