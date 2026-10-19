# 0012 — Case-scoped authorization, field-level rules and the audit log

Status: Accepted (Phase 2)

## Context

A law firm's cases are confidential even inside the firm. Four roles were
agreed: Administrator, Advocate, Paralegal and Client. Advocates see only the
cases they lead or are assigned to; Paralegals only the cases they are
assigned to, and may change only the court and the opposing party.

## Decision

- **One place for the rules:** `server/lexflow/authz.py` derives the user's
  relation to a case (admin, lead, associate, paralegal, client, none) and an
  `ALLOWED` table maps each action to the relations that may take it.
  `FIELD_ACTIONS` gives the action each editable field needs. The case detail
  reports `permissions` so the screens show only what the server would allow;
  the server checks every action again.
- **Not found, not forbidden:** a case (or its documents, hearings, client) the
  user may not see answers 404, exactly like one that does not exist. A visible
  case with a forbidden action answers 403 (`forbidden`, or
  `field-not-permitted` naming the fields). Lists are scoped in SQL
  (`visible_cases`), never filtered after loading.
- **Case teams** (`case_members`) give associates and paralegals their access;
  the Administrator or the lead manages the team.
- **Archived cases** are kept in full, read-only for everyone (409
  `case-archived`), and left out of default lists until an Administrator
  restores them.
- **Audit log:** sign-ins, refusals, every change and every document read are
  recorded in `audit_events` with the actor's name and role as they were.
  Details are whitelisted; keys that look like secrets are rejected. Successes
  are written only after the change commits (so a rolled-back change leaves no
  false entry); refusals and sign-in failures are written in an independent
  transaction. A trigger rejects UPDATE and DELETE.

## Consequences

- The audit log is append-only through the application and the database, but
  **not tamper-proof**: someone with database administrator rights can disable
  the trigger. The viewer says so.
- Every rule has a test, and each was checked to fail when its line of code was
  removed (the execution log lists these mutation checks).
- Adding a role or an action means adding it to `ALLOWED` and the tests; the
  front end's copy of the table (`src/test/mockApi.ts`) is for tests only.
