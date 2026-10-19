# Phase 2 + 2b execution log

Durable record of the Phase 2 (secure core) and Phase 2b (supporting workflows)
implementation: what was done, the commands run and their actual results, and
known limitations. Newest milestone last.

## Ground rules for this run

- No commits, pushes or remotes. Recovery points are saved outside the
  repository (a patch against HEAD plus a tar of untracked files) after each
  milestone.
- `docs/DEVELOPMENT_BRIEF.md` is not modified (excluded via `.git/info/exclude`).
- The development database `lexflow` is **never migrated** without a verified
  backup, a restore check into a scratch database, and the user's explicit
  approval. Tests use only `lexflow_test` (pytest), scratch `*_test*` databases
  (migration tests) and `lexflow_e2e` (Playwright), each recreated automatically.
- Secrets (passwords, session tokens, cookies, database URLs) are never printed
  or logged.

## M0 - Baseline (2026-10-19)

| Item | Result |
|---|---|
| Branch / HEAD | `master` / `7edfb75` (21 commits); working tree clean, no stashes |
| Brief | sha256 `274ecaed…c2ec`, excluded via `.git/info/exclude:9` |
| Databases | `DATABASE_URL` -> `lexflow` (dev, revision 0001: 6 cases, 26 documents, 5 users, 6 clients, 5 hearings, 22 timeline events); `TEST_DATABASE_URL` -> `lexflow_test`; E2E uses `lexflow_e2e` |
| Running processes | a Phase 1 API on 127.0.0.1:8000 (started earlier in this session); PostgreSQL container `lexflow-db-1` |
| `ruff check` / `ruff format --check` / `mypy` | clean (44 files / 42 source files) |
| `pytest` | **160 passed** |
| `export_openapi.py --check` | up to date |
| `npm run check` | exit 0, **80 tests**, build ok |
| `npx playwright test` | **11 passed** |

Changes since the last recorded baseline: none (HEAD and tree identical).

### Decisions in force (from the approved plan)

Four roles (Administrator, Advocate, Paralegal, Client); opaque server-side
sessions in HttpOnly cookies (a deviation from the brief's JWT, recorded in
ADR 0011); administrator/CLI provisioning, no self-registration; Advocates see
only cases they lead or are assigned to; Paralegals see assigned cases, upload
documents, manage hearings and may edit only court name and opposing party;
clients use a separate portal (Phase 2b) with explicitly shared documents;
cases are archived, documents soft-deleted (restore: Administrator or lead
Advocate; permanent purge only through a guarded CLI); fictional sample data on
reserved domains, Aryan Goyal kept as the sample Advocate; lockout after 5
consecutive failures for 15 minutes (the 6th attempt is the first refused).

## M1 - Account, session and audit-log schema (done)

Migration `0002_accounts_sessions_audit`: `users` gains `client_id` (FK
`clients`, RESTRICT, **not unique** - several contacts may represent one client),
`password_hash`, `is_active`, `must_change_password`, `temp_password_expires_at`,
`failed_login_count`, `locked_until`, `last_login_at`, `updated_at`; checks
`client_link` (Client role <=> client_id), `login_needs_email`,
`failed_login_count_non_negative`. New `sessions` (SHA-256 token hash only,
unique, format-checked; CASCADE from users) and `audit_events` (no FKs, actor
name/role snapshot, JSONB details, row trigger rejecting UPDATE/DELETE).

| Command | Result |
|---|---|
| `pytest tests/test_migrations.py tests/test_accounts_schema.py` | 11 passed (round trip, models match migrations, populated upgrade 0001 -> head -> 0001 keeps every row) |
| `pytest` (full) | **169 passed** |
| ruff / ruff format / mypy | clean |
| `export_openapi.py --check` | unchanged |

**Not applied to the development database `lexflow`** (still at 0001): awaits
backup, restore verification and approval.

## M2 - Fictional sample people on reserved domains (done)

`src/data/mockData.ts`: advocates are now `{name, email}` with
`@lexflow.test` addresses (Aryan Goyal kept); client e-mails moved to `.example`
domains; phone numbers start `+91 0` (no real Indian number does).
`scripts/export-sample-data.mjs` refuses any sample contact on a non-reserved
domain or with a reachable-looking phone number (checked: a real-looking number
is rejected). The loader brings contact details of existing **sample** rows up
to date on re-seeding (never touches non-sample rows) and never sets passwords.

| Command | Result |
|---|---|
| `pytest` | **172 passed** (new: unreachable contacts, no passwords from seeding, sample-only updates) |
| `npm run check` | exit 0, 80 tests |

## M3 - Sign-in, sessions, CSRF/Origin protection, lockout, CLI (done)

- Argon2id (`argon2-cffi` 25.1.0, pinned; RFC 9106 low-memory defaults; test-only
  fast profile refused outside `LEXFLOW_ENV=test`). Policy 12-128 characters, not
  the e-mail/name, spaces significant.
- Sessions: 256-bit `secrets.token_urlsafe(32)` tokens, SHA-256 stored only;
  idle 30 min, absolute 12 h, revocation on logout / password change /
  deactivation; new token at every sign-in. Cookie `lexflow_session` (HttpOnly,
  SameSite=Strict, Path=/, no Max-Age; `__Host-` + Secure when
  `LEXFLOW_COOKIE_SECURE=true`).
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
  `POST /api/auth/password` (current password required; ends other sessions).
  Every refused sign-in: identical 401 `invalid-credentials`, dummy hash
  verification for unknown/disabled accounts; real reason only in the audit log.
  Only Administrator and Advocate may sign in at this stage.
- Lockout: 5th consecutive failure locks for 15 minutes; 6th attempt refused even
  with the right password; attempts during a lock neither count nor extend it.
  Counters and audit rows go through independently committed sessions.
- CSRF: unsafe requests need `X-LexFlow-Request: 1`; `Origin` must be in an exact
  allow-list; a request carrying the session cookie must name its origin. Vite
  dev/preview CORS turned off. The front end's `apiFetch` sends the header; the
  MSW fake rejects changes without it (removing the header fails 9 tests).
- `python -m lexflow.cli.users create|set-password|unlock|disable|enable|list`:
  passwords only from a hidden prompt or `--password-stdin`, never as arguments,
  never printed; audited as "command line (<OS user>)".
- `python -m lexflow` additionally refuses `LEXFLOW_ENV=production` without
  `LEXFLOW_COOKIE_SECURE=true`, or while a sample account can sign in.

| Command | Result |
|---|---|
| `pytest` | **218 passed** (auth 33, committed-transaction auth 2, CLI 7, CSRF/Origin rewrite, start-up refusals) |
| mutation: independent commit removed | `test_failures_and_lockout_survive_the_failed_requests` fails |
| ruff / ruff format / mypy | clean (55 files) |
| `export_openapi.py --check` | regenerated for `/api/auth/*`, then up to date |
| `npm run check` | exit 0, 80 tests |
| `npx playwright test` | **11 passed** (Phase 1 flows through the CSRF header and exact-origin rule) |

## M4 - Real sign-in in the front end; every API route needs a session (done)

Backend (deny by default, two layers):
- `SessionGateMiddleware` (`lexflow/auth/gate.py`): non-public `/api/*` requests
  without a well-formed session cookie get 401 before any body is read (public:
  `GET /api/health`, `POST /api/auth/login`, `POST /api/auth/logout`). Unknown
  paths also answer 401 to anonymous callers.
- `require_user` on every other router (validates the session in the database;
  403 `password-change-required` while a temporary password is pending).
- The upload route parses its multipart body itself, after authentication
  (`openapi_extra` documents the body); the service runs in the thread pool.
- Mutation checks: removing the router dependency fails the forged-cookie test;
  removing the gate fails the unknown-path tests.

Front end:
- `AuthContext` reads the user from `GET /api/auth/me`; nothing about the
  session in `localStorage` (the Phase 1 `lexflow.auth` key is removed at start).
  Sign-in, sign-out and any 401 `not-authenticated` drop every cached query, so
  the next person never sees the previous person's data (strengthened test: the
  next user's list is delayed and the old titles must not appear meanwhile;
  removing the cache clearing fails 2 tests).
- Login page: no pre-filled credentials, one generic refusal message, honest
  note about administrator-created accounts; development-only hint
  (`import.meta.env.DEV`). New change-password page (also the forced one after a
  temporary password); top bar links to it.
- MSW fake API mirrors the session gate, `/auth/*`, the forced password change
  and the sign-in roles.

E2E: each run creates a random 32-character password, passes it to
`e2e.py prepare` in the environment only, stores it in git-ignored
`e2e/.state/credentials.json`, and saves signed-in storage states. New
`auth.spec.ts`: form sign-in/sign-out, replayed cookie refused, generic
refusal, lockout (6th attempt refused), CSRF header and no CORS through Vite.

| Command | Result |
|---|---|
| `pytest` | **226 passed** (deny-by-default route walk via the OpenAPI document, forged cookie, pending temporary password, anonymous upload refused with 0 body reads) |
| `npm run check` | exit 0, **91 tests** |
| `npx playwright test` | **15 passed**; the run password does not appear in `api.log` |

## M5 - Backend authorization and object-level case isolation (done)

- Migration `0003_case_members`: case teams (`associate` Advocates, `paralegal`
  Paralegals); the lead stays in `cases.lead_advocate_id`.
- `lexflow/authz.py`: relationship to a case (admin / lead / associate /
  paralegal / client / none) -> allowed actions (`ALLOWED`) and per-field rules
  for PATCH (`FIELD_ACTIONS`). Lists are scoped in SQL (`visible_cases`); by-id
  loads give 404 `case-not-found` / `document-not-found` when the case is not
  visible (identical to a missing id), 403 when visible but not permitted; both
  audited as `access.denied`. A field the user may not change is refused even if
  unchanged, and refuses the whole request before anything is written.
- Staff routers require Administrator/Advocate/Paralegal (a Client session gets
  403 on every staff route). Advocates open cases only as their own lead;
  Paralegals cannot open cases; leads must be active Advocates; changing lead or
  client is Administrator-only (a new lead leaves the team). Uploads check access
  before the body is read. Upcoming hearings, clients and the client picker
  (`/api/clients/options`, names only, Administrators and Advocates) are scoped.
- Timeline entries now carry the signed-in actor; `case.created`,
  `case.updated`, `document.uploaded/downloaded/deleted` audited after commit.
- Paralegals may now sign in (their scoping is enforced and tested).
- Front end: case detail carries `permissions`; the form uses the client picker;
  the MSW fake mirrors the rules (default test user: an Administrator).

| Command | Result |
|---|---|
| `pytest tests/test_case_access.py` | **71 passed** (6 people x every endpoint; set comparisons; refused changes change nothing) |
| mutations: advocates see all / paralegal status / field check off / document visibility off / any lead | 4 / 2 / 9 / 2 / 1 failures; restored byte-for-byte |
| `pytest` | **297 passed** |
| `npm run check` | exit 0, 91 tests |
| `npx playwright test` | 15 passed |

## M6 - Role-specific screens and Paralegal permissions (done)

- `src/lib/roles.ts`: "New Case" only for Administrators and Advocates (cases
  list, dashboard, empty state); Paralegals get an explanation at
  `/app/cases/new` and the client picker is not even requested.
- New-case form: an Advocate's lead picker is locked to themselves ("You lead the
  cases you open."); Administrators choose any active advocate.
- Documents tab follows the case's `permissions`: upload only when allowed,
  "Remove" only for the Administrator or lead advocate.
- Workspace header shows the user's access ("Lead advocate", "Paralegal on the
  case team", ...).
- E2E accounts: an assigned Paralegal (`e2e.paralegal@lexflow.test`) and an
  outsider Advocate (sample Rajat Deshpande). `roles.spec.ts`: the Paralegal sees
  one case, uploads, has no Remove button, and the API refuses delete and
  closing (403); the outsider gets "Case not found" and API 404s for a case id
  learned from another account.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **97 tests** (new `roles.test.tsx`) |
| `npx playwright test` | **17 passed** |
| `pytest` | 297 passed |

## M7 - Case editing, status, archive, case teams, audit (done)

Back end (no new tables beyond migration 0004 `cases.archived_at` /
`archived_by_id`, prepared earlier in M7; not applied to `lexflow`):

- `PATCH /api/cases/{id}` checks each field against the user's relation
  (`authz.FIELD_ACTIONS`): Advocates on the case edit details and status, a
  Paralegal only `courtName` and `opposingParty`, only an Administrator changes
  the lead or the client (403 `field-not-permitted`, naming the fields). The
  timeline entry names the person and carries a timestamp (`recordedAt`); the
  audit log records `case.updated` with the field names (not their values).
- `POST /api/cases/{id}/archive` and `/unarchive` (Administrators): an archived
  case keeps everything, is read-only for everyone (409 `case-archived` for
  edits, uploads, deletions and team changes), and is left out of the case list
  (`?archived=include|only` brings it back) and of upcoming hearings.
- Case teams: `POST /api/cases/{id}/team` and `DELETE .../team/{userId}` (the
  Administrator or the lead); `GET /api/staff` lists active Advocates and
  Paralegals (names and roles only). Joining or leaving grants or removes access
  at once.
- Fixed a real ordering bug found by a flaky test: timeline entries were
  stamped with PostgreSQL `now()`, which is fixed for a whole transaction, so
  two entries in one transaction could come back in either order. They are now
  stamped by the application (`TimelineEvent.created_at` Python default; the
  server default is unchanged, so no migration). New test
  `test_changes_on_the_same_day_stay_in_the_order_they_were_made`.

Front end:

- `src/pages/EditCasePage.tsx` (`/app/cases/:id/edit`): shows only the fields the
  user may change, sends only the fields that changed (blank optional text
  clears it), checks title and summary first, puts server reasons beside the
  field, and explains when nothing may be edited (including archived cases).
- Workspace header: "Edit case", "Archive case" with an in-page confirmation
  (focus moves to the confirm button; Cancel returns it), "Restore case", an
  Archived badge and a read-only notice.
- Overview: a Case Team card (lead plus members; add from `/api/staff`, remove,
  for the Administrator or lead only); timeline entries made in LexFlow show the
  time and the person.
- Case list: "Show archived" toggle and an Archived badge.
- Option lists moved to `src/lib/caseOptions.ts` (shared by both forms).
- Fake API (`src/test/mockApi.ts`) mirrors PATCH, archive/unarchive, team, staff,
  the archived filter and the archived 409s.

Tests: `src/pages/caseChanges.test.tsx` (12), `e2e/case-changes.spec.ts` (4;
each test puts the sample case back, so specs stay order-independent).
Front-end mutation checks (each guard broken in turn, then restored
byte-for-byte): sending unchanged fields, offering Archive without permission,
offering team changes without permission. Each made the new tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **109 tests** |
| `npx playwright test` | **21 passed** |
| `pytest` | **319 passed** (12 consecutive full runs); ruff, ruff format, mypy clean |

Unexplained: one full `pytest` run (immediately after a `git stash` / `stash
pop` of `models.py` used to try the test without the fix) reported
`1 failed, 318 passed`; the failing test's name was not captured, and 12 later
runs passed. Recorded rather than ignored; to watch in M15.

## M8 - Soft-deleted documents, restore, guarded purge command (done)

Migration **0005** (`0005_document_soft_delete.py`, prepared, **not applied to
`lexflow`**): `documents.uploaded_by_id`, `deleted_at`, `deleted_by_id` (FKs to
users, `ON DELETE SET NULL`), check `deleted_by_id IS NULL OR deleted_at IS NOT
NULL`, and the per-case unique name index becomes partial (`WHERE deleted_at IS
NULL`) so a deleted document's name can be reused. The downgrade refuses (and
changes nothing) while a deleted document shares a name with another on its case.

- `DELETE /api/documents/{id}` is now soft: the record and file are kept; the
  document disappears from the case, its count, listings and downloads (404).
- `GET /api/cases/{id}/documents/deleted` (new action `VIEW_DELETED_DOCUMENTS`,
  Administrator or lead; still allowed on archived cases, read-only) and
  `POST /api/documents/{id}/restore` (Administrator or lead; 409 `duplicate`
  while a live document has the same name; 409 `case-archived` on archived
  cases). Audit: `document.deleted`, `document.restored`.
- Documents record who uploaded them (`uploadedBy` in the API; "added by" in the UI).
- `python -m lexflow.cli.documents list-deleted | purge`: purge selects deleted
  documents by `--older-than-days N` or `--document ID`, always previews first
  and changes nothing without `--confirm N` matching the previewed count; never
  touches live documents or archived cases; locks each row and re-checks it is
  still deleted; removes the row, then the file; audits `document.purged` as
  "command line (<OS user>)". Nothing purges automatically.
- Front end: "Removed X. It can be restored from Deleted Documents below.";
  a Deleted Documents card (Administrator or lead only, list never requested
  otherwise) with Restore and clear conflict messages.

Behaviour change, tests updated to match (not weakened): three tests asserted
hard deletion (`test_delete_removes_record_and_file`, the front-end "removes a
document on the server", and the E2E documents test). They now assert that the
record and file are kept, hidden from every ordinary read, and shown under
Deleted Documents.

New tests: `test_document_lifecycle.py` (13), `test_cli_documents.py` (10),
migration test for the partial index and the downgrade guard,
`documentLifecycle.test.tsx` (4), E2E restore round-trip (byte-identical file).
Mutation checks (each restored byte-for-byte): Deleted Documents shown without
permission, purge of a live document, deleted documents readable, purge
without a matching `--confirm`. All four made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **113 tests** |
| `npx playwright test` | **22 passed** |
| `pytest` | **343 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M9 - Basic hearings: schedule, change, cancel (done)

Migration **0006** (`0006_hearing_status.py`, prepared, **not applied to
`lexflow`**): `hearings.status` (`Scheduled`/`Cancelled`, default `Scheduled`
so existing hearings stay scheduled), `cancelled_at`, `cancelled_by_id`,
`cancellation_reason` (≤ 500), `created_by_id`, `updated_at`; checks that the
status and `cancelled_at` agree. The downgrade refuses while cancelled hearings
exist (it would silently turn them back into scheduled ones).

- `POST /api/cases/{id}/hearings`, `PATCH /api/hearings/{id}`,
  `POST /api/hearings/{id}/cancel` (any staff on the case, `MANAGE_HEARINGS`;
  404 `hearing-not-found` for a case the user cannot see, denial audited;
  409 `case-archived`; 409 `hearing-cancelled` when editing a cancelled one).
  Dates cannot be in the past (an unchanged past date is not re-checked on
  edit); time is `HH:MM` or blank ("to be notified"); court and purpose
  required, ≤ 200 characters. Hearings are never deleted.
- Cancelled hearings stay on the case with the reason but no longer count as
  the next hearing (case list and detail) or appear among upcoming hearings.
- Timeline entries ("Hearing scheduled / updated / cancelled") name the person;
  audit `hearing.scheduled`, `hearing.updated` (field names), `hearing.cancelled`.
- Front end: a Hearings card on the overview with "Schedule hearing", per-hearing
  change and cancel (with optional reason, focus on the reason box), cancelled
  hearings struck through with the reason; hidden controls when not allowed or
  archived; edits send only changed fields.
- Firm-wide Hearings page: still Phase 2b (M11), as decided.

Contract change: `HearingOut` gained `status` and `cancellationReason`; two
exact-shape tests in `test_cases.py` were updated to include them, and the
0005 migration test now pins revision 0005 instead of `head`.

New tests: `test_hearings.py` (26), migration test for 0006,
`hearings.test.tsx` (6), E2E hearing round-trip. Mutation checks (restored
byte-for-byte): cancelled hearings counted as next, past dates accepted,
cancelled hearings editable, controls ignoring permissions, edits sending
unchanged fields. All five made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **119 tests** |
| `npx playwright test` | **23 passed** |
| `pytest` | **370 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M10 - Client management (Phase 2b) (done)

No migration (who added or changed a client is in the audit log).

- `GET /api/clients/{id}` (details plus the client's cases the user may see, and
  `canEdit`), `POST /api/clients` (Administrators and Advocates),
  `PATCH /api/clients/{id}` (the Administrator, or an Advocate who leads or is an
  associate on one of the client's cases; Paralegals 403, audited as denied).
  A client none of whose cases the user may see answers 404 `client-not-found`
  (Administrators see all). Clients cannot be deleted (405): cases refer to them.
- Checks: name ≥ 2 characters, a plausible e-mail, phone of 7 to 20 digits, spaces,
  `+`, `-` or brackets, company ≤ 200 characters. Audit `client.created`,
  `client.updated` (field names only, never the values).
- Front end: Clients in the sidebar; `/app/clients` (search),
  `/app/clients/new`, `/app/clients/:id` (contact details, edit in place for
  those allowed, the client's cases, "Open a case"). The new-case form accepts
  `?client=` and preselects it.
- Found by a new test and fixed before logging: an Advocate who added a client
  would then have been sent to that client's page and told "Client not found"
  (they see clients only through their cases, and the new client has none).
  They now go straight to the new-case form with the client chosen, and are
  told why the client appears on their list only once they work on a case.

New tests: `test_clients.py` (28), `clients.test.tsx` (6), E2E: an
Administrator adds a client, opens the first case from the client page, and
another advocate gets 404 for that client. Mutation checks (restored
byte-for-byte): Paralegals allowed to edit clients, unscoped client list, Edit
offered without permission. All three made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **125 tests** |
| `npx playwright test` | **24 passed** |
| `pytest` | **398 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M11 - Firm-wide Hearings page (Phase 2b) (done)

No migration.

- `GET /api/hearings?from=&to=&includeCancelled=&limit=`: hearings on the cases
  the user may see (Administrators: all), archived cases left out, cancelled
  ones only on request, soonest first, each with the case title, number and
  lead advocate. Defaults: from today, for 30 days. The range may span at most
  a year and must not end before it starts (422 on `to`); `limit` 1 to 500
  (default 200), with `truncated: true` when more matched.
- Front end: Hearings in the sidebar; `/app/hearings` with "Next 7 days",
  "Next 30 days" and "Past 30 days" presets, custom From/To dates (an inverted
  range is explained and not sent), "Show cancelled", hearings grouped by day
  and linked to their cases; a notice when the list was cut short.

New tests: `test_hearing_schedule.py` (13), `hearingsPage.test.tsx` (5), E2E:
the paralegal sees a Sattvik hearing on the page, an unrelated advocate does
not. Mutation checks (restored byte-for-byte): unscoped schedule, cancelled
hearings always included, unlimited range. All three made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **130 tests** |
| `npx playwright test` | **25 passed** |
| `pytest` | **411 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M12 - Client identity, explicit sharing, client portal, isolation (Phase 2b) (done)

Migration **0007** (`0007_document_sharing.py`, prepared, **not applied to
`lexflow`**): `documents.shared_with_client_at`, `shared_by_id` (FK, `SET NULL`),
and checks: who shared needs when; a deleted document is never shared; only a
stored file can be shared. The downgrade only withdraws sharing.

Identity: a Client account is a `users` row with role `Client` and its
`client_id` (the check from migration 0002 makes one without the other
impossible; tested). Accounts are created with
`python -m lexflow.cli.users create --role Client --client-id <id>`.

Order followed, as decided: portal and isolation first, then sign-in.

1. Sharing (staff): `POST /api/documents/{id}/share` and `/unshare` (Advocates
   on the case and Administrators, `SHARE_DOCUMENT`; Paralegals 403; 422
   `no-file` for sample records; 409 on archived cases). Deleting a document
   stops sharing it; restoring does not share it again. Audit `document.shared`,
   `document.unshared`; `sharedWithClientAt` in `DocumentOut`.
2. Portal API, mounted with `require_roles(CLIENT)`: `GET /api/portal/cases`,
   `GET /api/portal/cases/{id}`, `GET /api/portal/documents/{id}/download`.
   Every query filters on the account's own `client_id`; archived cases leave
   the portal; no internal details (summary, priority, opposing party, team,
   timeline, cancelled hearings or their reasons); only scheduled hearings from
   today; only shared, live documents. Anything else answers 404. Client
   downloads are audited like staff ones.
3. Isolation proven (`tests/test_portal.py`, 21 tests), with sessions opened
   directly while Client sign-in was still off: a sweep of **every** staff route
   from the OpenAPI document answers 403 to a Client account (28 routes), every
   portal route answers 403 to Administrators, Advocates and Paralegals, and a
   second client can neither list nor fetch the first client's case or files.
   Six mutation checks (client filter on downloads, shared-only filter, client
   filter on cases, portal role guard, staff role guard, deleting stops sharing)
   each made these tests fail.
4. Only then: `CLIENT` added to `SIGN_IN_ROLES`. The test that asserted Clients
   could not sign in was replaced by one that a Client signs in, reaches the
   portal (200) and not the staff API (403).

Front end: `/portal` (Client Portal shell, own cases, case page with coming
hearings and shared documents, password change at `/portal/account/password`).
The staff app sends Client accounts to the portal and the portal sends staff to
the app; return-to links are honoured only inside the account's own area. Staff
see "Shared with client" on documents and a share/stop-sharing control (only
where allowed and only for stored files). E2E has a Client account
(`e2e.client@client.example`, sample client c-005) with a saved session.

New tests: `test_portal.py` (21), updated `test_auth.py`, `portal.test.tsx` (7),
updated router test, `e2e/portal.spec.ts` (2: share, download byte-identical,
unshare, 404; Client refused on staff API and redirected from `/app`).
Front-end mutation checks (layout guards both ways, share control without
permission) all made tests fail; the share-control check first survived (the
paralegal test only looked at sample records) and the test was strengthened.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **137 tests** |
| `npx playwright test` | **27 passed** |
| `pytest` | **432 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M13 - User administration screens (Phase 2b) (done)

No migration. Same rules as `python -m lexflow.cli.users`, now also in the app.

- `/api/admin/users` (list), `POST /api/admin/users` (create with a temporary
  password the administrator types; the person must replace it at first
  sign-in; it is never returned, logged or audited), `PATCH` (name and e-mail;
  the role cannot change, 422), `.../disable` (ends their sessions),
  `.../enable`, `.../unlock`, `.../password` (new temporary password, ends their
  sessions). Mounted with `require_roles(ADMINISTRATOR)`: every route answers
  403 to everyone else (tested by a sweep).
- Guards: no disabling or resetting your own account (409); the last active
  Administrator cannot be disabled (409, defence in depth); duplicate e-mail
  addresses, Client accounts without a client (or non-clients with one), weak
  passwords and passwords equal to the e-mail or name are refused (422, on the
  field). Audit `user.created` (role, "via administration"), `user.updated`
  (field names), `user.disabled/enabled/unlocked/password_set`.
- Front end: "Administration" in the sidebar for Administrators only;
  `/app/admin/users` lists accounts with their state (active, disabled, locked,
  no password, must change password, last sign-in) and offers New Account,
  edit, temporary password, unlock, disable/enable (never on your own row).

New tests: `test_admin_users.py` (22), `admin.test.tsx` (5), `e2e/admin.spec.ts`
(an account created in the UI signs in, is held at the password page, changes
it, gets in, and is signed out the moment it is disabled). Mutation checks
(restored byte-for-byte): admin routes open to all roles, self-disable allowed,
last-administrator guard removed, new accounts not forced to change password,
Administration shown to everyone. All five made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **142 tests** |
| `npx playwright test` | **28 passed** |
| `pytest` | **454 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M14 - Audit-log viewer (Phase 2b) (done)

No migration.

- `GET /api/admin/audit` (Administrators only; read-only, other methods 405):
  newest first, filters `action` (exact, or a prefix ending in a dot such as
  `document.`), `outcome`, `actorId`, `caseId`, `from`/`to` (whole days in the
  firm's time zone; an inverted range is 422), keyset pages (`limit` 1 to 200,
  `nextBefore` cursor; an unknown cursor is 422). Each entry carries the case
  number where there is one and the whitelisted `details`; no password, token
  or cookie ever appears (tested).
- Front end: Administration now has "Accounts" and "Audit log" tabs;
  `/app/admin/audit` with action-group, outcome and date filters, links to
  cases, readable details and "Load older entries".
- Wording, as decided: the page and the API description say the log cannot be
  changed through LexFlow and the database rejects updates and deletions, but
  that it is **not tamper-proof** (someone with database administrator access
  could alter it).

New tests: `test_audit_view.py` (14), audit tests in `admin.test.tsx` (3), an
E2E check (sign-in entries listed; no password fields; Advocate, Paralegal and
Client get 403). Mutation checks (restored byte-for-byte): outcome filter
ignored, repeated entries across pages, prefix matching broken, audit page shown
to everyone. All four made tests fail.

| Command | Result |
|---|---|
| `npm run check` | exit 0, **145 tests** |
| `npx playwright test` | **29 passed** |
| `pytest` | **468 passed**; ruff, ruff format, mypy, OpenAPI check clean |

## M15 - Full regression, security review, documentation, database gate (done; migration awaiting approval)

### Regression (final state)

| Command | Runs | Result |
|---|---|---|
| `pytest` (server) | 3 consecutive | **468 passed** each time (the unexplained single failure noted in M7 did not recur in 20+ full runs since) |
| `ruff check .`, `ruff format --check .`, `mypy` (as CI runs it), `export_openapi.py --check` | 1 | clean, 80 source files |
| `npm run check` | 1 (+1 extra `vitest run`) | exit 0, **146 tests**, build OK |
| `npx playwright test` | 2 consecutive | **29 passed** each time |

### Security review (self-review; no external tools)

Checked by reading code and by tests: no logger call carries a password,
token or cookie; no `print` in server code outside the command-line tools;
sessions re-check `is_active`, expiry, idle time and revocation on every
request; no `dangerouslySetInnerHTML`/`innerHTML`/`eval` in the front end;
return-to links are honoured only inside the account's own area (new tests for
`/application`, `/portalx`, `//evil.example`, staff into the portal, clients
into the app); secrets and artifacts are git-ignored (`server/.env`,
`e2e/.state/` with the run password and saved sessions, `server/var/` with
uploads and backups, `test-results/`, `playwright-report/`); CI uploads only the
API request log (method, path, status). Findings that remain are listed in the
final report (no IP-level rate limiting; lockout can be triggered by anyone who
knows an address; Advocates see every client's name in the new-case list;
dependency vulnerability scanning not run, because it would send the dependency
list to an external service).

### Documentation

`README.md` and `server/README.md` rewritten for Phase 2; `server/.env.example`
documents the new settings (defaults match `lexflow/config.py`); ADRs 0011 to
0014 added and indexed; ADR 0005 marked "superseded in part by 0011" (status
line only). CI needed no change. `docs/DEVELOPMENT_BRIEF.md` untouched
(last modified 2026-10-14, before this run; excluded from git).

### Development database gate

1. Target resolved from `server/.env`: `postgresql+psycopg://lexflow:***@127.0.0.1:5432/lexflow`;
   `select current_database()` = `lexflow` (container `lexflow-db-1`,
   postgres:17). Revision **0001**. Rows: cases 6, clients 6, documents 26,
   hearings 5, timeline_events 22, users 5, case_number_counters 2.
2. Backup (read-only for `lexflow`):
   `docker exec lexflow-db-1 pg_dump -U lexflow -d lexflow -Fc -f /tmp/lexflow-20261019-phase2-pre-migration.dump`,
   copied to `server/var/backups/lexflow-20261019-phase2-pre-migration.dump`
   (23,768 bytes, SHA-256 `a23f85a0fd00272b2748926bb5e2063116223787c0261f51367dcb23baba870d`,
   git-ignored; 8 table-data entries).
3. Restore verified into a new scratch database:
   `createdb -U lexflow lexflow_restore_check`, then
   `pg_restore -U lexflow -d lexflow_restore_check --no-owner --exit-on-error <dump>`.
4. Comparison: identical row counts; identical per-table content checksums
   (md5 of every row, all 7 tables); `pg_dump --schema-only` identical except the
   random `\restrict` session keys pg_dump writes; no case without its client or
   lead, no document without its case.
5. Rehearsal on the scratch copy only (script refuses any other database):
   `upgrade head` (0001 to 0007) kept every row count; the 5 people stay active
   with no password and no lockout (nobody can sign in until an Administrator is
   created); 5 hearings Scheduled; 26 documents live and unshared; 6 cases not
   archived. `downgrade 0001` and `upgrade head` again also kept every count.
   `lexflow` re-checked afterwards: still **0001**.
6. **Stopped here.** Migrations 0002 to 0007 have **not** been applied to
   `lexflow`; that waits for explicit approval. The scratch database
   `lexflow_restore_check` (now at 0007) is left for inspection.

## After M15 - Migrations applied to `lexflow`; masked password prompt

**Migrations (approved by the user).** Backup re-verified (SHA-256 matches).
`alembic upgrade head` in `server/` moved `lexflow` from 0001 to **0007**
(exit 0). Verified afterwards: revision 0007 (head); every existing table has
the same row count and its original columns are identical (checksum over the
pre-migration column set); new fields hold their defaults (5 users active, no
password; 5 hearings Scheduled; 26 documents live and unshared; 6 cases not
archived); the audit append-only trigger exists; `alembic check` finds no
differences. No Administrator exists yet.

**First attempt at provisioning, stopped.** The CLI was opened in a separate
PowerShell window; the user reported that the hidden `getpass` prompt seemed
not to accept keys (Windows `getpass` echoes nothing at all). The window was
closed (exit 0xC000013A); no account, no audit entry, nothing changed.

**Masked prompt.** `server/lexflow/cli/masked_input.py` (new) replaces
`getpass` as the CLI's default prompt: one `*` per character, Backspace/Delete
remove the last character and its `*`, Ctrl+U clears, Enter finishes, Ctrl+C
or Ctrl+D (empty line) cancel; arrow/function keys, escape sequences, Tab and
other control characters are ignored; input is capped at 1,024 characters.
Keys come from `msvcrt.getwch()` on Windows (as `getpass` did) and from the
terminal in non-echoing raw mode on macOS/Linux (always restored); non-terminal
input falls back to `getpass`. Nothing but the prompt, `*`, erasures and a
newline is written, to stderr. `server/lexflow/cli/users.py` uses it and now
answers Ctrl+C/Ctrl+D with "Cancelled. Nothing was changed." (exit 130);
password policy, Argon2id hashing, the confirmation check and account creation
are unchanged (the password is read before anything is added or committed).
The masked prompt shows the password's length, which `getpass` did not; that is
the requested trade-off.

Tests: `server/tests/test_masked_input.py`, 22 passed (no database needed),
plus a POSIX pseudo-terminal test defined only off Windows (runs in CI on
Linux). Six mutation checks (mask echoing the character, Backspace not removing
it, Ctrl+C ignored, control characters accepted, cancellation not handled,
mismatch accepted) each made the tests fail. Real Windows console smoke test
(keys typed into a new console through `WriteConsoleInputW`): `a x ⌫ b Enter`
returned `ab` showing `PW: **\b \b*`; `a b Ctrl+C` cancelled showing `PW: **`.
ruff, ruff format, mypy (Windows and `--platform linux`) clean. The CLI's
database-backed tests (`test_cli_users.py`) were not re-run, because they
recreate `lexflow_test`.
