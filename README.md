# Drive-Thru LiveKit Agent

> **Status: Under development** — APIs, schemas, and workflows are still evolving. Expect breaking changes.

An AI-powered drive-thru ordering system. Customers place orders by speaking naturally with a real-time voice agent. Managers configure menu items, agent behavior, and branch settings through an admin panel.

## Architecture

```
Customer (Browser) ──WebSocket──▶ Voice Agent (Python/LiveKit) ──HTTP──▶ Admin API (FastAPI) ──SQL──▶ PostgreSQL
                                        ▲                                        │
                                        │                                        │
                                   Wake word                              Admin UI (React/Vite)
                                   (ONNX in-browser)
```

Three components work together:

| Component | Technology | Port | Description |
|-----------|-----------|------|-------------|
| **Admin API** | FastAPI + SQLModel + PostgreSQL | `:8000` | JWT-authenticated REST API for CRUD on branches, menu items, documents, agent configs, parser config, users, sessions |
| **Voice Agent** | LiveKit Agents (Python) | dynamic (LiveKit) | Real-time STT → LLM → TTS pipeline with menu ordering function tools |
| **Admin UI + Customer Page** | React 19 + Vite 8 + Mantine UI | `:5173` | Dual-purpose SPA: customer voice-ordering page + admin panel with role-based navigation |

## Features

### Customer Page (`/` or `/agent`)
- **Wake word detection** — ONNX model runs in-browser; say "hey livekit" (configurable) to start hands-free
- **Voice ordering** — real-time conversation with the agent via LiveKit WebSocket
- **Audio visualizer** — animated bars/grid/wave/radial/aura while the agent speaks
- **Live menu panel** — browse categories, prices, dietary badges, offers
- **Live cart panel** — items, quantities, running total (updated via RPC from the agent)
- **Human handoff** — agent can transfer to a staff member with recorded notes

### Admin Panel (`/platform/*`)
JWT-protected routes with role-based access:

| Route | Page | Roles | Description |
|-------|------|-------|-------------|
| `/platform` | Dashboard | admin, manager, staff | Overview: menu items, documents, configs, branches |
| `/platform/menu` | Menu | admin, manager, staff | CRUD items, sizes (S/M/L/XL), dietary info, offers, tags, favourites, search |
| `/platform/listen` | Listen In | admin, manager, staff | Browse sessions and orders |
| `/platform/documents` | Documents | admin, manager | Upload menu files (PDF/image/text/CSV) → LLM extracts items → review → confirm |
| `/platform/agent-configs` | Agent Configs | admin, manager | List/create/edit/delete config presets, toggle active |
| `/platform/agent-configs/:id` | Edit Config | admin, manager | Full form: STT, LLM, TTS, VAD, turn detection, wake words, UI theme, instructions |
| `/platform/parser-config` | Parser Config | admin | Choose which LLM parses uploaded menu documents |
| `/platform/branches` | Branches | admin | CRUD franchise branches (address, currency, timezone) |
| `/platform/users` | Users | admin | CRUD users (roles, branch assignment) |
| `/platform/login` | Login | all | JWT login |

### Agent Configuration
Agent behavior is driven by a JSON config stored server-side and fetched per-session. The config covers:

- **STT** — provider (Deepgram/AssemblyAI), model, language, keyterms for bias
- **LLM** — provider (OpenAI/Anthropic/Google), model, temperature, parallel tool calls
- **TTS** — provider (Cartesia/ElevenLabs), model, voice ID, language
- **VAD** — enable/disable, activation threshold, min speech/silence duration
- **Turn detection** — mode (multilingual/english/vad/stt/none)
- **Session** — max tool steps, allow interruptions, endpointing delays, preemptive generation
- **Background audio** — ambience noise toggle and volume
- **Wake words** — enable, trigger phrases, detection threshold, ONNX model URL
- **UI** — visualizer variant, accent colour, customer heading

### Wake Word Detection
Client-side ONNX Runtime Web detects a trigger phrase before the customer connects:

1. Microphone audio captured at 16 kHz via Web Audio API
2. Mel spectrogram computed in-browser (FFT → power spectrum → mel filterbank → log)
3. 96-frame context window fed to a pre-trained ONNX classifier (`hey_livekit.onnx`)
4. On score > threshold, the hook fires and connects to the agent

Falls back gracefully to a tap button if unsupported or on error.

### Menu Document Pipeline
1. Upload a menu file (PDF, image, markdown, CSV, or plain text)
2. LLM extracts items with categories, sizes, pricing, dietary info
3. Review parsed output in the UI
4. Confirm to merge or replace items in the menu database

### Session Lifecycle
1. Customer opens the page → wake word listens or shows "Start order" button
2. `POST /agent/connection` creates a LiveKit room, mints a token, and inserts a `Session` row
3. LiveKit dispatches the job → voice agent picks it up
4. Agent fetches config by `config_id` from room metadata
5. Menu pushed to customer UI via RPC (`set_menu_content`)
6. Cart updated in real-time via RPC (`set_cart_content`)
7. Customer disconnects → `PATCH /sessions/by-room/{room_name}/complete`
8. Handoff notes posted if agent transferred to human

## Prerequisites

- Python 3.13+
- Node.js 20+ and npm
- PostgreSQL (or SQLite for light dev — the server auto-detects)
- A [LiveKit Cloud](https://cloud.livekit.io) project (or self-hosted LiveKit server)
- API keys for your chosen providers:
  - STT: Deepgram (or AssemblyAI)
  - LLM: OpenAI (or Anthropic, Google)
  - TTS: Cartesia (or ElevenLabs)

## Setup

### 1. Install dependencies

```bash
make install
```

This runs `uv sync` for both Python packages (server + voice-agent) and `npm install` for the client.

### 2. Configure environment

**Admin API** — `backend/server/.env`:

```env
DATABASE_URL=postgresql+psycopg://user:pass@localhost/drivethru
# Or for SQLite: sqlite:///./dev.db

JWT_SECRET=change-me-to-a-long-random-string

ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme

LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

AGENT_API_KEY=shared-secret-between-server-and-agent

# At least one LLM key for menu parsing
OPENAI_API_KEY=sk-...
```

**Voice Agent** — `backend/voice-agent/.env`:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...

SERVER_URL=http://localhost:8000
AGENT_API_KEY=shared-secret-between-server-and-agent
```

### 3. Run

```bash
# All three components (terminal multiplexing via Make)
make start-all

# Or individually:
make server      # FastAPI on http://localhost:8000 (hot-reload)
make agent       # Voice agent (connects to LiveKit)
make client      # Vite dev server on http://localhost:5173
```

Default admin login: `admin` / `changeme`

## Project Structure

```
├── backend/
│   ├── server/                    # FastAPI admin API
│   │   ├── src/server/
│   │   │   ├── app.py            # App factory, lifespan, CORS, router registration
│   │   │   ├── db.py             # Engine, session, auto-migration, bootstrapping
│   │   │   ├── deps.py           # Auth dependencies (get_current_user, require_branch_resource)
│   │   │   ├── models.py         # 10 SQLModel tables (users, branches, menu, documents, etc.)
│   │   │   ├── security.py       # bcrypt hashing + JWT create/verify
│   │   │   ├── settings.py       # Environment-based settings
│   │   │   ├── routers/          # auth, users, branches, menu, documents, agent_configs,
│   │   │   │                     # parser_config, connection, sessions
│   │   │   ├── schemas/          # Pydantic models (shared JSON contract)
│   │   │   └── parsing/          # Menu document upload → extract → LLM → confirm pipeline
│   │   └── tests/test_api.py     # Integration tests (SQLite in-memory)
│   └── voice-agent/              # LiveKit voice agent
│       └── src/voice_agent/
│           ├── agent.py          # DriveThruAgent (@agent, @function_tool methods)
│           ├── config.py         # AgentConfig schema (mirrored in server schemas)
│           ├── config_loader.py  # Config resolution: inline > server fetch > defaults
│           ├── database.py       # FakeDB with hardcoded menu fallback + COMMON_INSTRUCTIONS
│           ├── menu_client.py    # Live menu fetch from admin API + cutlery items
│           ├── models.py         # Plugin factory (STT/LLM/TTS/VAD/turn_detection)
│           └── order.py          # OrderState data classes
│
├── client/                       # React SPA
│   └── src/
│       ├── admin/pages/          # AgentConfigEdit, AgentConfigs, Branches, Dashboard,
│       │                         # Documents, ListenIn, Menu, ParserConfig, Users
│       ├── customer/             # CustomerPage, CartPanel, MenuPanel, Visualizers,
│       │                         # useWakeWord (ONNX hook)
│       ├── api/                  # client.ts (fetch wrapper), hooks.ts (React Query), types.ts
│       ├── components/           # auth/ (AuthContext, LoginPage, ProtectedRoute),
│       │                         # AsyncState, PageHeader, TriStateSelect, NumberOrNull
│       └── lib/                  # agentConfigDefaults, notify, options
│
├── Makefile                      # install, server, agent, client, start-all, test, etc.
└── README.md
```

## API Endpoints

All admin API endpoints live under the `/agent` prefix and require JWT auth (except login).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Get JWT token |
| GET | `/auth/me` | Current user info |
| GET/POST/PATCH/DELETE | `/users` | User CRUD |
| GET/POST/PATCH/DELETE | `/branches` | Branch CRUD |
| GET/POST/PATCH/DELETE | `/menu` | Menu item CRUD |
| GET/POST | `/documents` | Upload and list menu documents |
| PATCH | `/documents/{id}` | Update parsed items |
| POST | `/documents/{id}/confirm` | Confirm parsed items into menu |
| GET/POST | `/agent-configs` | List and create agent configs |
| GET/PATCH/DELETE | `/agent-configs/{id}` | Get, update, delete agent config |
| GET/PUT | `/parser-config` | Read/write parser config |
| GET | `/sessions` | List sessions |
| GET | `/sessions/{id}` | Get session with orders |
| PATCH | `/sessions/by-room/{room}/complete` | Mark session complete |
| POST | `/sessions/by-room/{room}/handoff-notes` | Store handoff notes |
| GET | `/connection/config` | Lightweight config preview (no session created) |
| POST | `/connection` | Create LiveKit room + token + session |

## Database

**Primary:** PostgreSQL (production). **Dev:** SQLite via `DATABASE_URL=sqlite:///./dev.db`.

The server auto-creates tables and runs idempotent migrations on startup. It also seeds:
- Default parser config (singleton row)
- Default "Main" branch
- Admin user from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars

### Tables

| Table | Rows | Notes |
|-------|------|-------|
| `users` | auth | JWT, bcrypt passwords, roles (admin/manager/staff) |
| `branches` | org | Address, currency, timezone |
| `menu_items` | menu | Categories, dietary, tags, offers, pricing, calories |
| `menu_item_sizes` | menu | Per-item size options with cascade delete |
| `documents` | ingest | Uploaded files, parsed JSON, status tracking |
| `agent_configs` | config | JSON-stored agent configuration presets |
| `parser_config` | config | Singleton: LLM provider/model for menu parsing |
| `sessions` | orders | Customer sessions with timeline/status |
| `orders` | orders | Subtotal/tax/total, linked to session |
| `order_items` | orders | Line items snapshotted at order time |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `server` | Run FastAPI with hot-reload (kills stale process on 8000) |
| `agent` | Run voice agent in dev mode |
| `client` | Run Vite dev server |
| `start` | Run server + agent concurrently |
| `start-all` | Run server + agent + client concurrently |
| `test` | Run all test suites |
| `install` | Install all dependencies (uv + npm) |
| `kill-port` | Kill process on a given port |

## Roles

| Role | Scope |
|------|-------|
| Admin | Full access — all branches, users, settings |
| Manager | Their assigned branch — menu, documents, agent configs |
| Staff | Read-only — orders, sessions (branch-scoped) |

Branch scoping is enforced server-side via `require_branch_resource`: admins see everything, managers/staff are filtered to their `branch_id`.

## License

MIT
