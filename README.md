# openDocket

**This project was built to test the capabilities of vibe coding with DeepSeek V4 Flash.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript 5](https://img.shields.io/badge/TypeScript-5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Tests: 109](https://img.shields.io/badge/tests-109-blueviolet.svg)](backend/tests)

**openDocket** is a self-hostable, multi-user contract manager. It keeps track of
your contracts, key dates, counterparties, documents and costs in one place — and
warns you before something renews or expires.

It ships with a strong, insurance-ready feature set (German insurance categories,
*Versicherungsnehmer* / policyholder tracking, *Versicherungsnummer* handling,
German/English/Turkish UI), while remaining a general-purpose contract manager for
rentals, utilities, subscriptions, loans and memberships.

> **Status:** early-stage `0.1.0`. The core product is feature-complete and
> self-hostable today; see [Roadmap & known limitations](#roadmap--known-limitations)
> for what is deliberately not built yet.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Security & data isolation](#security--data-isolation)
- [Quick start (Docker Compose)](#quick-start-docker-compose)
- [Configuration](#configuration)
- [AI features](#ai-features)
- [Local development](#local-development)
- [Tests](#tests)
- [Project structure](#project-structure)
- [API overview](#api-overview)
- [Roadmap & known limitations](#roadmap--known-limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Contracts

- **Full contract lifecycle** — title, status (`draft` / `active` / `expired` /
  `terminated`), category, counterparty, optional policyholder, effective date,
  expiry/renewal date, notice period in days, notes, value + ISO 4217 currency,
  tags and attachments.
- **Versicherungsnummer** — a human-friendly, collision-resistant insurance/contract
  number (`VN-XXXXXXXX`, ambiguity-free alphabet) that is auto-generated when empty.
- **36 predefined categories in 8 groups** — KFZ, Haftpflicht, Kranken, Vorsorge,
  Unfall, Sach, Rechtsschutz and Sonstige. Stored as stable keys, labelled in the UI
  language, filterable by individual category *or* by group.
- **Card board view** with an archive for expired/terminated contracts.
- **Renewal = duplicate** — clone a contract (including tags) as a fresh draft and
  update the dates.
- **Search & filters** — full-text `ILIKE` search across title, notes, counterparty,
  category and tags, plus filters for status, category, category group, tag,
  counterparty and an "expiring within N days" window.
- **Tags** — per-user tag vocabulary with reuse, ordering preserved and dedicated
  create/delete endpoints.

### Dates, dashboard & reminders (no email yet)

- **Dashboard** with total contract count, contracts expiring within 90 days
  (sorted, with days-left and expiry warnings), counts by status and counts by
  category.
- **Expiry/notice awareness** — notice period stored in days; contract list and
  dashboard surface days remaining. Automatic *email* reminders are not implemented.

### Counterparties & policyholders

- **Counterparties** as reusable, structured entities — companies *or* persons, with
  optional email, phone and notes, plus an overview page ("all contracts with Acme").
- **Auto-creation on contract save** — typing a new counterparty name creates it
  (case-insensitive match with fuzzy fallback), so you never block on master data.
- **Versicherungsnehmer (policyholder) page** — a dedicated overview of the people
  contracts belong to, auto-filled from scanned documents, with their own contract
  list.

### Documents

- **Multiple files per contract** — PDF, PNG/JPEG/GIF/WebP, DOC/DOCX/ODT and TXT,
  **25 MB** per file.
- **UUID storage** — files are stored on a local volume under random names; the
  original filename and MIME type are kept in the database.
- **Access-controlled streaming** — downloads always go through an authenticated,
  ACL-checked endpoint; there is no public file path.
- **Export/backup** — one-click ZIP containing `manifest.json` (all contracts,
  counterparties, categories, tags, dates, values and file metadata) plus a `files/`
  directory with the original binaries.

### Scan-to-contract (OCR + optional AI)

- Upload PDFs, images or text files during contract creation and let openDocket
  pre-fill the form; uploaded files stay attached after review.
- **Text extraction** — embedded PDF text via `pypdf`, Tesseract OCR fallback for
  scanned PDFs and images (German + English + Turkish language packs).
- **Heuristics engine** — regex-based parsing of titles, counterparties,
  policyholders, policy numbers, German/English dates, recurring amounts (premium vs.
  sum insured, with currency disambiguation) and notice periods.
- **Optional LLM extraction** — any OpenAI-compatible chat endpoint can refine the
  result and normalise categories; results are validated and clamped before use.
- **Vision mode** — rendered page images (up to 6 pages, max 1568 px, JPEG) are sent
  to multimodal models, with automatic fallback to text-only if the model rejects
  images.

### AI Assistant

- Built-in **chat** that answers both *"how do I use openDocket?"* and questions about
  **your own contracts** ("which contracts expire in the next 60 days?", "what do I
  pay for my car insurance?").
- **Grounded context** — only contracts the requesting user can access are included
  (owned or shared), capped at 200 contracts / ~24 000 characters, with prior
  conversation history sanitised and truncated to 40 turns.
- **Strict instructions** — the model is told to answer only from the provided list,
  never invent data, and reply in the user's language.
- **Read-only** — the assistant cannot create, edit, delete or share anything.

### Users, sharing & administration

- **Multi-user with hard data isolation** from day one — every user sees only their own
  data plus contracts explicitly shared with them.
- **Per-contract sharing** with role `viewer` (read-only). Owners have full control;
  viewers can read and download but cannot edit, trash or delete.
- **Admin-invite only** — no open registration. The first admin is bootstrapped from
  environment variables on first boot. Admins can invite, enable/disable, reset
  passwords of and delete users — but **cannot see other users' contracts**.
- **Self-service profile** — display name, own password change and per-user
  light/dark theme persisted on the account.
- **Trash / soft delete** — deleted contracts go to a per-owner trash, can be
  restored, and are purged automatically after 30 days (files included).

### Experience

- **Optional one-click demo account** — off by default (`ENABLE_DEMO=true` to
  enable) because its credentials are public; when enabled it seeds a rich,
  realistic sample dataset (contracts, counterparties, policyholders, upcoming
  expiries).
- **Multi-language UI** — English, German and Turkish, persisted per browser.
- **Light/dark theme** with a toggle.
- **Responsive SPA** with a card-based contract board.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend framework | **FastAPI** (async), **Uvicorn** |
| ORM / DB layer | **SQLAlchemy 2.0** (async) + **asyncpg** |
| Database | **PostgreSQL 16** (SQLite in-memory for tests) |
| Migrations | **Alembic** (7 revisions) |
| Validation / config | **Pydantic v2** + **pydantic-settings** |
| Auth | **fastapi-users** cookie strategy, DB-backed access tokens, **argon2** (`pwdlib`) |
| Document parsing | **pypdf**, **PyMuPDF (fitz)**, **pytesseract** (Tesseract OCR), **Pillow** |
| HTTP client | **httpx** (OpenAI-compatible chat completions) |
| Frontend | **React 18** + **TypeScript 5** + **Vite 5** |
| Routing / state | **react-router-dom** 6, React context |
| i18n | **i18next** + **react-i18next** (EN / DE / TR) |
| Styling | plain CSS (`styles.css`), theme via CSS variables |
| Web server | **nginx** (static SPA + `/api` reverse proxy) |
| Packaging | **Docker** + **Docker Compose** (Postgres + backend + frontend) |
| Testing | **pytest** + **pytest-asyncio** + httpx `ASGITransport` — 109 tests |
| Linting | **ruff** (line length 100, target py312) |
| Runtime versions | Python **3.12+**, Node **22** (build image) |
| License | **MIT** |

Frontend dependencies: `react`, `react-dom`, `react-router-dom`, `i18next`,
`react-i18next`. Dev: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react*`.

Backend dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`,
`asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `fastapi-users[sqlalchemy]`,
`email-validator`, `python-multipart`, `itsdangerous`, `pwdlib[argon2]`, `httpx`,
`pypdf`, `pymupdf`, `pytesseract`, `Pillow`, `pytest`, `pytest-asyncio`.

---

## Architecture

```
Browser ──► nginx :80 ──► /api/* ──► FastAPI (uvicorn :8000) ──► PostgreSQL 16
              │                            │
              └── serves built React SPA    ├── /api/contracts/*/files/*  (ACL-checked)
                                           │        └──► disk volume (/data/files)
                                           └── optional ──► OpenAI-compatible LLM endpoint
```

- The **frontend container** serves the compiled Vite SPA and reverse-proxies `/api/`
  to the backend (`proxy_read_timeout 300s` to allow slow OCR/AI requests). Long-lived
  cache headers are set for hashed assets, `no-store` for `index.html`.
- The **backend container** runs `alembic upgrade head` and then Uvicorn.
- **Files live on a named Docker volume** (`filedata`); Postgres data on `pgdata`.
- All contract queries are scoped by `owner_id` **or** a share row for the current user
  through a single reusable query helper, so the ACL cannot be forgotten per route.
- Settings are read once via a cached `pydantic-settings` object; the admin account and
  optional demo dataset are ensured on application startup, and a background task purges
  expired trash daily.

---

## Security & data isolation

- **Session cookie auth** — `fastapi-users` cookie transport with an `httpOnly`,
  `SameSite=Lax` cookie (`opendocket_session`), 30-day lifetime, backed by
  database-stored access tokens. Passwords are hashed with **argon2**.
- **CSRF hardening** — a middleware enforces a same-origin check against the `Origin`
  header on every state-changing request (`POST`/`PUT`/`PATCH`/`DELETE`), honouring
  `X-Forwarded-Proto` behind a TLS terminator.
- **Per-resource ACL dependencies** — routes declare either *accessible* (owner **or**
  viewer) or *owned* (owner only) access; unauthorised resources return `404` rather
  than leaking existence.
- **Per-user isolation everywhere** — contracts, counterparties, tags, shares and
  files are all owner-scoped. Tags are uniquely constrained per user
  (`uq_tags_owner_name`), shares per contract+user.
- **Admins are not super-readers** — admin endpoints manage accounts only and never
  expose other users' contracts.
- **File safety** — extension allow-list with server-side MIME mapping, 25 MB cap,
  random UUID storage names (no path traversal, no original-name collisions), and no
  direct disk access from the browser.
- **AI key handling** — API keys configured in the browser are kept in `localStorage`
  and sent per request; the server never persists them. If a user points openDocket at
  their own endpoint/model without supplying a key, the server's key is deliberately
  **not** forwarded. This holds for both the assistant and scan-to-contract.
- **SSRF protection on AI calls** — the server only contacts hosts listed in
  `LLM_ALLOWED_HOSTS` (public provider hosts are pre-listed) or the host of the
  admin-configured `LLM_BASE_URL`. Everything else is refused, which blocks loopback,
  private and link-local targets such as cloud metadata services.
- **Session revocation** — changing your own password immediately invalidates every
  *other* session for that account; an admin password reset or deactivating a user
  invalidates all of their sessions.
- **Rate limiting & browser hardening** — nginx applies per-IP request limits (strict on
  login, demo login, chat, document scanning and provider tests) and sends
  `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` and
  `Referrer-Policy` on every response.
- **AI data handling** — document text and contract data are sent to whichever provider
  is configured, so point openDocket at a provider you trust.
- **Soft delete is recoverable** — trashed contracts are hidden from all normal queries
  and only visible (and restorable) by their owner.

Operational notes: set a strong `SECRET` and `POSTGRES_PASSWORD`, and set
`COOKIE_SECURE=true` when serving over HTTPS.

---

## Quick start (Docker Compose)

**Requirements:** Docker with the Compose plugin.

```bash
git clone https://github.com/karslioguzhan/openDocket.git
cd openDocket

# 1. Create your environment file
cp .env.example .env
#    then edit .env: set ADMIN_EMAIL, ADMIN_PASSWORD and SECRET

# 2. Build and start Postgres + backend + frontend
docker compose up --build -d

# 3. Open the app
#    http://localhost:8080
```

On first boot the backend runs the Alembic migrations and creates the admin account from
`ADMIN_EMAIL`/`ADMIN_PASSWORD`. The public demo account is **disabled by default**; set
`ENABLE_DEMO=true` to seed it and show the login screen's **"Try the demo"** button.

Useful commands:

```bash
docker compose logs -f backend     # follow backend logs
docker compose down                # stop the stack (volumes are kept)
docker compose down -v             # stop and delete database + file volumes
```

Change the published port with `PORT=9000 docker compose up -d`.

---

## Configuration

All backend settings come from environment variables (case-insensitive, read via
`pydantic-settings`). Values in `.env` are applied when running outside Docker.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://opendocket:opendocket@localhost:5432/opendocket` | SQLAlchemy async DSN. |
| `SECRET` | `change-me` | Secret for tokens/sessions. **Change in production.** |
| `FILE_STORAGE_DIR` | `./data/files` | Directory for uploaded files (Docker: `/data/files`). |
| `COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS. |
| `SESSION_LIFETIME_SECONDS` | `2592000` (30 days) | Session/token lifetime. |
| `ADMIN_EMAIL` | *(empty)* | Email of the admin bootstrapped on first boot. |
| `ADMIN_PASSWORD` | *(empty)* | Password for that admin. |
| `ADMIN_IS_SUPERUSER` | `true` | Whether the bootstrapped admin is a superuser. |
| `AUTO_CREATE_TABLES` | `false` | Create tables from models instead of migrations (dev convenience). |
| `ENABLE_DEMO` | `false` | Show the one-click demo login and seed its sample data. Only enable on a throwaway instance — the credentials are public. |
| `TRASH_PURGE_DAYS` | `30` | Days a trashed contract is kept before permanent purge. |
| `LLM_BASE_URL` | *(empty)* | Optional shared OpenAI-compatible endpoint. |
| `LLM_API_KEY` | *(empty)* | Optional shared API key. |
| `LLM_MODEL` | *(empty)* | Optional shared model id. |
| `LLM_ALLOWED_HOSTS` | `opencode.ai,api.openai.com,openrouter.ai,api.groq.com,api.deepseek.com` | Comma-separated `host` or `host:port` entries the server may contact for AI requests. Requests to any other host are refused (SSRF protection). |
| `LLM_ALLOW_PRIVATE` | `false` | Allow AI endpoints on any host, including private/loopback addresses. Needed for local providers such as Ollama; leave `false` on any instance other people can reach. |

Compose-level variables (used by `docker-compose.yml`): `POSTGRES_PASSWORD`, `PORT`,
`SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `COOKIE_SECURE`, `ENABLE_DEMO`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL`, `LLM_ALLOWED_HOSTS`, `LLM_ALLOW_PRIVATE`.

See [`.env.example`](.env.example) and [`backend/.env.example`](backend/.env.example).

---

## AI features

Scan-to-contract autofill and the AI Assistant share one provider configuration. Any
**OpenAI-compatible** `/chat/completions` endpoint works.

Configure it either:

1. **Server-wide** via `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, or
2. **Per browser** in **Settings** — the provider/model/key/vision preference is stored
   in `localStorage` and sent with each request.

The Settings page ships presets for:

| Preset | Base URL | Default model | Vision |
| --- | --- | --- | --- |
| OpenCode Zen | `https://opencode.ai/zen/v1` | `deepseek-v4-flash` | ✅ |
| OpenCode Go | `https://opencode.ai/zen/go/v1` | `deepseek-v4-flash` | ✅ |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | ✅ |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | ✅ |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | — |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | — |
| Local (Ollama/LM Studio) | `http://host.docker.internal:11434/v1` | `llama3` | — |
| Custom | *(yours)* | *(yours)* | — |

Endpoints are restricted to `LLM_ALLOWED_HOSTS` plus the host of the admin-configured
`LLM_BASE_URL`, so the server cannot be pointed at internal services. To use the
**Local (Ollama/LM Studio)** preset or any custom/internal endpoint, either add its host
to `LLM_ALLOWED_HOSTS` or set `LLM_ALLOW_PRIVATE=true`.

A **Test connection** button (backed by `POST /api/llm/test`) validates the endpoint
before you rely on it. Without any provider configured, the app still works fully —
scan-to-contract simply falls back to OCR + heuristics and the assistant reports that
no provider is set.

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point at a local Postgres and let the app create its schema
export DATABASE_URL="postgresql+asyncpg://opendocket:opendocket@localhost:5432/opendocket"
export SECRET="dev-secret"
export AUTO_CREATE_TABLES=true
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="admin-password-123"

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are then at <http://localhost:8000/docs>.

OCR requires the Tesseract binary plus language data
(`tesseract-ocr`, `tesseract-ocr-deu`, `tesseract-ocr-eng`, `tesseract-ocr-tur`).

### Frontend

```bash
cd frontend
npm ci
npm run dev     # Vite dev server, http://localhost:5173
```

`vite.config.ts` proxies `/api` to `http://localhost:8080` (the Compose stack). When
running the backend directly on port `8000`, change the proxy `target` accordingly.
`npm run build` performs a full `tsc -b` type-check and produces `dist/`.

---

## Tests

The backend has **109 pytest tests** covering auth, ACLs/sharing, contracts CRUD,
filtering, files, extraction/OCR heuristics, LLM integration, the AI assistant, the
dashboard, demo seeding, export, user administration and the security hardening
(AI-endpoint allow-list, API-key isolation, session revocation, trash write-protection). Tests run against an
in-memory SQLite database via httpx's `ASGITransport`, so no Postgres is required.

```bash
cd backend
pip install -r requirements.txt
pytest
```

Configuration lives in `backend/pyproject.toml`: `asyncio_mode = "auto"`, test path
`tests/`. Linting: `ruff check .`.

---

## Project structure

```
openDocket/
├── docker-compose.yml          # postgres + backend + frontend
├── .env.example                # Compose/deployment configuration
├── PLAN.md                     # original product & architecture decisions
├── LICENSE                     # MIT
├── backend/
│   ├── Dockerfile              # python:3.12-slim + Tesseract (deu/eng/tur)
│   ├── requirements.txt
│   ├── pyproject.toml          # pytest + ruff config
│   ├── alembic/versions/       # 7 migrations, 0001_initial … 0007_versicherungsnehmer
│   ├── app/
│   │   ├── main.py             # app factory, lifespan, CSRF middleware, health
│   │   ├── config.py           # pydantic-settings
│   │   ├── db.py               # async engine/session, Base, timestamps
│   │   ├── auth.py             # fastapi-users setup, cookie + DB token strategy
│   │   ├── dependencies.py     # ACL query helpers & per-resource access deps
│   │   ├── storage.py          # upload allow-list, 25 MB cap, storage dir
│   │   ├── models/             # user, contract, contract_file, share, access_token
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── routers/            # auth, users, contracts, counterparties, meta,
│   │   │                       # extraction, llm, chat, files, dashboard, export
│   │   └── services/           # admin bootstrap & trash purge, demo seed,
│   │                           # extraction (OCR + heuristics + LLM), assistant
│   └── tests/                  # 109 tests
└── frontend/
    ├── Dockerfile              # node:22 build → nginx:alpine
    ├── nginx.conf              # SPA fallback, /api proxy, rate limits + security headers
    ├── public/theme-init.js    # pre-render theme bootstrap (CSP-friendly)
    ├── vite.config.ts
    └── src/
        ├── App.tsx             # routes
        ├── api.ts, auth.tsx, theme.tsx, llmConfig.ts, types.ts
        ├── components/         # Layout, ContractCard, UI primitives, toggles
        ├── i18n/               # en / de / tr locales
        ├── pages/              # Dashboard, ContractList, ContractDetail,
        │                       # ContractForm, Counterparties,
        │                       # Versicherungsnehmer, Chat, Trash, Admin,
        │                       # Settings, Login
        └── styles.css
```

---

## API overview

All endpoints are prefixed with `/api` and (except auth/health) require a session
cookie. State-changing requests are origin-checked.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/demo-login` |
| Account | `GET/PATCH /api/users/me`, `PATCH /api/users/me/theme`, `POST /api/users/me/change-password` |
| Admin | `GET/POST /api/users`, `PATCH/DELETE /api/users/{user_id}` *(superuser)* |
| Contracts | `GET/POST /api/contracts`, `GET/PATCH/DELETE /api/contracts/{id}`, `POST /api/contracts/{id}/restore`, `POST /api/contracts/{id}/duplicate` |
| Sharing | `POST /api/contracts/{id}/shares`, `DELETE /api/contracts/{id}/shares/{user_id}` |
| Files | `POST /api/contracts/{id}/files`, `GET/DELETE /api/contracts/{id}/files/{file_id}` |
| Scan | `POST /api/contracts/extract` (multipart, optional per-request LLM config + vision flag) |
| AI | `POST /api/chat`, `POST /api/llm/test` |
| Counterparties | `GET/POST /api/counterparties`, `GET/PATCH/DELETE /api/counterparties/{id}` |
| Metadata | `GET /api/meta/categories`, `GET/POST /api/meta/tags`, `DELETE /api/meta/tags/{tag_id}` |
| Dashboard | `GET /api/dashboard` |
| Export | `GET /api/export` (ZIP) |
| Health | `GET /api/health` |

Contract list filters: `status`, `category`, `group`, `counterparty_id`, `tag`,
`search`, `expiring_days` (1–365) and `trashed`.

---

## Roadmap & known limitations

Implemented beyond the original MVP: scan-to-contract with OCR/AI, vision extraction,
AI assistant, export/backup, multi-language UI, themes, demo mode and insurance-specific
modelling.

Deliberately **not** implemented yet:

- **Email reminders** for upcoming expiry/renewal (dashboard/expiry awareness only).
- **iCal / calendar export.**
- **Public REST API with tokens** for third-party integrations.
- **Editor role** — sharing is read-only (`viewer`); no per-contract editing by others.
- **Full-text search backend** — search uses `ILIKE` with substring matching; the
  planned `pg_trgm` index is not created by a migration yet.
- **E2E/browser tests and CI** — pytest coverage and a frontend type-check/build only.
- **DOC/DOCX/ODT text extraction** — these formats can be uploaded and stored, but
  scan-to-contract rejects them (PDF, images and TXT are extractable).
- **Registration, password-reset email, MFA** — accounts are admin-invited only.
- **Object storage / S3** — files live on a local Docker volume.
- **Frontend unit tests.**
- **Session tokens are stored unhashed** in the database (fastapi-users' DB strategy), so
  a database or backup leak exposes live sessions — protect the Postgres volume and its
  backups.
- **Share-by-email reveals whether an address is registered** (`404` vs `201`). nginx
  rate limits blunt enumeration but do not remove it.

---

## Contributing

Contributions are welcome. A few conventions keep the project coherent:

1. **Fork and branch** — use a descriptive branch name (`feat/…`, `fix/…`).
2. **Keep the ACL model intact** — new contract-scoped routes must use the
   accessible/owned dependencies rather than ad-hoc queries.
3. **Add tests** for backend behaviour, especially anything touching access rules.
4. **Run the checks before opening a PR:**
   ```bash
   cd backend && ruff check . && pytest
   cd ../frontend && npm run build
   ```
5. **Database changes go through Alembic** — add a new revision; do not edit existing
   migrations.
6. **UI text must be translatable** — add new strings to `en`, `de` *and* `tr` locale
   files.
7. **Never commit secrets or personal data** — `.env` and `backend/data/` are ignored;
   keep it that way.

Open an issue first for larger features so the approach can be agreed on.

---

## License

Released under the **MIT License**. See [LICENSE](LICENSE).

Copyright (c) 2026 karslioguzhan.
