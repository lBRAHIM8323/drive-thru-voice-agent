# Drive-Thru LiveKit Agent

> **Status: Under development** — APIs, schemas, and workflows are still evolving. Expect breaking changes.

An AI-powered drive-thru ordering system. Customers place orders by speaking with a voice agent in real time. Managers configure menu items, agent behavior, and branch settings through an admin panel.

## Architecture

```
Customer (Browser) ──WebSocket──▶ Voice Agent (Python/LiveKit) ──HTTP──▶ Admin API (FastAPI) ──SQL──▶ PostgreSQL
                                                                              ▲
                                                                              │
                                                                         Admin UI (React/Vite)
```

- **Voice Agent** (`backend/voice-agent/`) — LiveKit `AgentServer` that handles STT (Deepgram), LLM (OpenAI/Anthropic/Google), TTS (Cartesia/ElevenLabs), VAD (Silero), turn detection, and order management via function tools.
- **Admin API** (`backend/server/`) — FastAPI server with JWT auth, role-based access control, and CRUD endpoints for branches, menu items, documents, agent configs, and parser settings.
- **Admin UI** (`client/`) — React SPA with Mantine UI. Role-based sidebar navigation (admin sees everything, managers see only their branch, staff read-only).

## Quick Start

```bash
# Install dependencies
make install

# Start the admin API (http://localhost:8000)
make server

# Start the voice agent (connects to LiveKit)
make agent

# Start the React dev server (http://localhost:5173)
make client

# Or start all three together
make start-all
```

Default admin credentials: `admin` / `changeme` (set via `ADMIN_USERNAME`/`ADMIN_PASSWORD` in `backend/server/.env`).

## Project Structure

```
backend/
├── server/          # FastAPI admin API
│   ├── src/server/
│   │   ├── routers/    # auth, users, branches, menu, documents, agent_configs, parser_config, connection
│   │   ├── schemas/    # Pydantic models (JSON contract with voice-agent and client)
│   │   ├── models.py   # SQLModel database tables (10 tables)
│   │   ├── deps.py     # Auth dependencies (get_current_user, require_role, require_branch_resource)
│   │   ├── security.py # bcrypt + JWT
│   │   ├── parsing/    # Menu document upload → extract → LLM → review → confirm pipeline
│   │   └── db.py       # Engine, session, migrations, seeding
│   └── tests/
└── voice-agent/      # LiveKit voice agent
    └── src/voice_agent/
        ├── agent.py       # DriveThruAgent with function tools + cart RPC
        ├── config.py      # AgentConfig schema (mirrored by server)
        ├── config_loader.py  # Config resolution chain
        ├── database.py    # FakeDB (hardcoded McDonald's menu fallback)
        ├── menu_client.py # Live menu fetch from admin API
        ├── models.py      # Plugin factory (STT/LLM/TTS/VAD/turn detection)
        └── order.py       # Order state management

client/               # React SPA
├── src/
│   ├── admin/pages/     # Dashboard, Menu, Documents, Agent Configs, Branches, Users
│   ├── api/             # Fetch client, React Query hooks, TypeScript types
│   ├── components/auth/ # AuthContext, LoginPage, ProtectedRoute
│   └── customer/        # CustomerPage, CartPanel, Visualizers
```

## Roles

| Role    | Scope                                                       |
|---------|-------------------------------------------------------------|
| Admin   | Full access — all branches, users, settings                 |
| Manager | Their assigned branch only — menu, documents, agent configs |
| Staff   | Read-only access to their branch — orders, sessions         |

## Makefile Targets

| Target          | Description                               |
|-----------------|-------------------------------------------|
| `server`        | Run FastAPI (kills stale process on 8000) |
| `agent`         | Run voice agent in dev mode               |
| `client`        | Run Vite dev server                       |
| `start`         | Run server + agent concurrently           |
| `start-all`     | Run server + agent + client concurrently  |
| `test`          | Run all test suites                       |
| `kill-port`     | Kill process on a given port              |
| `install`       | Install all dependencies                  |
