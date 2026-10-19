# LexFlow API (`server/`)

FastAPI + PostgreSQL backend for LexFlow: accounts and sessions, case records
with role-based access, hearings, clients, document storage, the client portal
and the audit log.

> **Local use only, not deployed.** The API has real sign-in and access control
> (Phase 2), but it still listens on `127.0.0.1` only and has not been reviewed
> for deployment. Do not expose it to a network or put real client data in it.

## Requirements

- Python **3.12** (`py -3.12 --version`)
- Docker Desktop (for PostgreSQL 17 via Docker Compose)

## First-time setup (Windows, PowerShell)

```powershell
cd server

# 1. Local configuration. Edit .env and replace "change-me" with your own
#    password in POSTGRES_PASSWORD, DATABASE_URL and TEST_DATABASE_URL.
Copy-Item .env.example .env

# 2. Python environment with the pinned dependencies
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt

# 3. Database (binds to 127.0.0.1 only) and schema
docker compose up -d --wait
.venv\Scripts\python -m alembic upgrade head

# 4. The first Administrator (there is no self-registration). You are asked
#    for the password twice; it shows as * and is never displayed or logged.
.venv\Scripts\python -m lexflow.cli.users create --email you@example.com --name "Your Name" --role Administrator
```

An existing development database from Phase 1 needs migrations 0002 to 0007;
back it up first (see "Migrations" below).

## Everyday commands

```powershell
docker compose up -d --wait            # start PostgreSQL
.venv\Scripts\python -m lexflow        # API on http://127.0.0.1:8000 (docs: /docs)
docker compose stop                     # stop PostgreSQL (data is kept)
```

## Accounts

Four roles: **Administrator** (everything), **Advocate** (the cases they lead
or are assigned to), **Paralegal** (the cases they are assigned to; may change
only the court and the opposing party) and **Client** (the client portal:
their own matters and the documents shared with them). Accounts are created by
an Administrator, in the app (Administration → Accounts) or here:

```powershell
.venv\Scripts\python -m lexflow.cli.users create --email E --name N --role Advocate [--temporary]
.venv\Scripts\python -m lexflow.cli.users create --email E --name N --role Client --client-id <client id>
.venv\Scripts\python -m lexflow.cli.users set-password --email E [--temporary]
.venv\Scripts\python -m lexflow.cli.users unlock  --email E
.venv\Scripts\python -m lexflow.cli.users disable --email E    # also ends their sessions
.venv\Scripts\python -m lexflow.cli.users enable  --email E
.venv\Scripts\python -m lexflow.cli.users list
```

Passwords come from a masked prompt (asked twice; each character shows as `*`,
Backspace corrects, Ctrl+U clears, Ctrl+C cancels without changing anything) or,
for scripts, standard input with `--password-stdin`; never from the command line. A `--temporary`
password must be replaced at the next sign-in. Every change is audited as made
from the command line by your operating-system user.

## Sample data

```powershell
.venv\Scripts\python -m lexflow.seed
```

Loads the fictional sample cases, clients, advocates, hearings, timeline events
and document records (no files). It only runs when `LEXFLOW_ENV=development`.
Running it again adds nothing; it only refreshes the contact details of sample
rows. Sample rows have fixed ids and are marked `is_sample`, so the app labels
them. Sample people get addresses on `lexflow.test`, sample clients on
`.example` domains. Sample accounts have no password and cannot sign in until
you give one a password with the command above (production refuses to start
while a sample account can sign in).

## Deleted documents

Deleting a document in the app only hides it; the Administrator or the lead
advocate can restore it. Removing records and files for good is a separate,
deliberate step, never automatic:

```powershell
.venv\Scripts\python -m lexflow.cli.documents list-deleted [--case LF-2026-0001]
.venv\Scripts\python -m lexflow.cli.documents purge --older-than-days 90      # preview only
.venv\Scripts\python -m lexflow.cli.documents purge --older-than-days 90 --confirm 3
.venv\Scripts\python -m lexflow.cli.documents purge --document <id> --confirm 1
```

`purge` always shows what it would remove and changes nothing unless
`--confirm N` matches the number previewed. It never touches live documents or
documents on archived cases.

## Uploaded files

Files go to `LEXFLOW_UPLOAD_DIR` (default `server/var/uploads`, ignored by git),
named by a random key, never by the uploaded name. The limit is
`LEXFLOW_MAX_UPLOAD_BYTES` (default 25 MB), enforced while the request streams
in, and only after the uploader's access to the case is checked. Accepted: PDF,
Word (`.doc`, `.docx`), text and PNG/JPG/GIF/WebP images, and the contents must
match the extension. Files are not encrypted, scanned or backed up.

## Security model

See `docs/adr/0005`, `0011`, `0012` and `0014` for the reasoning.

- **Sessions:** opaque 256-bit tokens in an `HttpOnly`, `SameSite=Strict`
  cookie (`__Host-` and `Secure` with `LEXFLOW_COOKIE_SECURE=true`); only a hash
  is stored. They end after 30 minutes idle or 12 hours, on sign-out, on a
  password change and when an account is disabled. Passwords are hashed with
  Argon2id. The 5th consecutive wrong password locks the account for 15 minutes.
- **CSRF:** changes need the `X-LexFlow-Request: 1` header and an exact allowed
  `Origin` (`LEXFLOW_ALLOWED_ORIGINS`); no CORS is granted.
- **Deny by default:** everything but health, sign-in and sign-out needs a
  session; staff routes refuse Client accounts and the portal refuses staff;
  per-case and per-field rules live in `lexflow/authz.py`. A case you may not
  see answers 404.
- **Local-only:** the API binds to `127.0.0.1` and refuses requests for other
  `Host` names (DNS rebinding). In production mode it also refuses to start
  without `Secure` cookies.
- **Audit log:** sign-ins, refusals, changes and document reads, with
  whitelisted details (never passwords, tokens or cookies). Append-only through
  the app and a database trigger, but **not tamper-proof** against a database
  administrator.
- Errors never include stack traces, SQL or parameters.

## End-to-end support

`scripts/e2e.py prepare` recreates a separate `lexflow_e2e` database (the
`DATABASE_URL` server with a different database name, which must contain
`e2e`), migrates it, loads the sample data, creates the test accounts with the
run's random password (from `LEXFLOW_E2E_PASSWORD`, never a command argument)
and empties `var/e2e-uploads`; `scripts/e2e.py serve` runs the API against it on
port 8001. `npm run e2e` at the repository root does both for you.

## Checks

```powershell
.venv\Scripts\python -m pytest         # needs the database running
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\mypy
```

Tests use the database named in `TEST_DATABASE_URL` (its name must contain
`test`). They drop and recreate it at the start of every run and build the
schema with the real migrations, so they never touch the development database.

## Dependencies

Direct dependencies are listed in `requirements.in` and `requirements-dev.in`;
the fully pinned sets are generated with pip-tools:

```powershell
.venv\Scripts\pip-compile --strip-extras --output-file=requirements.txt requirements.in
.venv\Scripts\pip-compile --strip-extras --output-file=requirements-dev.txt requirements-dev.in
.venv\Scripts\pip-sync requirements.txt requirements-dev.txt
```

## Migrations

```powershell
.venv\Scripts\python -m alembic current            # which revision the database is at
.venv\Scripts\python -m alembic upgrade head       # apply
.venv\Scripts\python -m alembic downgrade -1       # undo the latest
.venv\Scripts\python -m alembic revision --autogenerate -m "describe change"
```

**Back up the development database before applying migrations**, and check the
backup restores:

```powershell
docker exec lexflow-db-1 pg_dump -U lexflow -d lexflow -Fc -f /tmp/lexflow.dump
docker cp lexflow-db-1:/tmp/lexflow.dump .\lexflow-backup.dump
```

Review every autogenerated migration by hand. `tests/test_migrations.py` fails
if the models and migrations disagree, and checks that data survives an
upgrade and that downgrades refuse rather than misrepresent data (deleted
documents sharing a name, cancelled hearings).
