# openDocket — Self-hostable Personal Contract Manager

## Decisions (locked)

**Product**
- Open-source (MIT) contract manager: track your contracts, key dates, and files.
- **MVP = core CRUD + tracking.** Reminders, OCR, iCal, public API are post-MVP.

**Multi-user & access**
- Multi-user from day one; **per-user data isolation** with **per-contract sharing**.
- Two permission levels: **owner** (full control) and **viewer** (read-only). No editors.
- **Admin invites only** (no open registration); admin is account manager only — invite, disable, reset passwords — and **cannot see others' contracts**.
- First admin bootstrapped from env vars on first run.
- **Soft delete / trash** (recoverable), purge after 30 days.

**Domain model**
- **Contract**: title, status (`Draft`/`Active`/`Expired`/`Terminated`), counterparty (FK), effective date, expiry/renewal date, notice-period days, notes, optional value + currency, category (**predefined enum**, grouped; stored as key string, labels localized in UI), tags, owner, shared-with ACL, `deleted_at`.
- **Counterparty**: structured entity (name + optional contact/notes) — enables "all contracts with Acme".
- **Files**: multiple per contract (PDF/image/docx/odt, 25 MB cap), original name + MIME stored.
- Renewal = duplicate + update dates (not a status).

**Stack**
- **Backend**: FastAPI + SQLAlchemy + Alembic + Pydantic.
- **DB**: PostgreSQL.
- **Auth**: `fastapi-users` cookie strategy — httpOnly session cookie + CSRF, argon2 hashing.
- **Frontend**: React SPA (Vite + TS), served by nginx in production.
- **Files**: local disk volume, UUID filenames, served via authenticated ACL-checking endpoint.
- **Deploy**: Docker Compose (`postgres` + `app` + `nginx`). One command to self-host.
- **Search**: ILIKE across title/counterparty/tags/category/notes with `pg_trgm` index; filters for status, category, tags, expiring window.
- **Dashboard**: expiring within 30/60/90 days (sorted), counts by status, contracts by category.
- **Export/backup**: download all contracts + metadata as JSON/zip (in v1).
- **Testing**: pytest for API + ACL rules (riskiest logic), frontend build check. No E2E in v1.
- **CI**: none in v1 — repo stays private.

## Architecture

```
Browser ──► nginx ──► /api/* ──► FastAPI (uvicorn) ──► PostgreSQL
              │                          │
              └── serves built React ────└── /api/files/* (ACL-checked) ──► disk volume
```

- Session cookie auth enforced by a FastAPI dependency on every route; all contract queries scoped by `owner_id` + ACL join.
- CSRF on all state-changing requests; same-origin enforcement.
- Env-var config: admin bootstrap, DB URL, file volume path, secret key.

## Build phases

1. **Backend skeleton**: FastAPI app, SQLAlchemy models + Alembic migrations, env-var bootstrap, `fastapi-users` auth + CSRF.
2. **ACL core**: per-contract share table, owner/viewer enforcement in a shared dependency, soft-delete/trash + purge job.
3. **Contract CRUD + search/filter**: ILIKE + `pg_trgm`, dashboard aggregate queries.
4. **Files**: upload/download via ACL-checked endpoints, UUID storage, type/size validation.
5. **Export**: JSON/zip dump + restore.
6. **Frontend**: Vite + TS SPA — login, dashboard, contract list/detail, counterparty list, share dialog, trash view, admin user management.
7. **Packaging**: Docker Compose + nginx, `docker-compose up` self-host story.
8. **Tests**: pytest coverage of API + ACL; build check in repo config.

## Defaults adopted
- Purge window **30 days**; notice period stored as integer days.
- Value stored as decimal + ISO 4217 currency code.
- English-only UI in v1; no rate limiting beyond basic login throttling.
- Counterparty contact info = optional email/phone/free-text notes.
- Trash visible to owners only.

## Deferred (post-MVP, schema already accommodates)
- Email reminders for expiry/renewal, OCR/full-text-in-PDF, iCal export, public API, Playwright E2E, CI/image publishing.
