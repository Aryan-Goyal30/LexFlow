# Batch 4: Milestones 7 and 8 (security and privacy review; real-model evaluation)

**Date:** 2026-10-26.

**What kind of review:** a **focused** review under a token budget, of
authentication, authorisation, documents, database isolation, secrets,
audit logs and external AI data flows. It reuses the work of Batches 2 and
3. It is **not a comprehensive security audit or a penetration test**, and
passing tests are not proof of security.

## Milestone 7: findings

**Fixed in this programme:**

| Defect | Batch | Fix and tests |
|---|---|---|
| Prompt injection: text in a document could support false facts, invented citations and fake contradictions | 3 | Validator `grounding-5`, `tests/test_prompt_injection.py` (21) |
| The same file under another name was accepted on one case (evidence counted twice) | 3 | 409 `duplicate-content` on upload and restore (3 tests) |
| `e2e.py prepare` could drop a database holding genuine judgments | 2 | `holds_genuine_judgments` guard; Playwright isolated in `lexflow_e2e_playwright` (tested) |
| Order-dependent test failure (audit events leaking between tests), present at `10a44c5` | 3 | Test scoped to its own events |

**No new high-impact defect** was found in Batch 4. Each area checked, with
its evidence:

| Area | Evidence | Assessment |
|---|---|---|
| Deny by default | `test_access_required`: every `/api` operation from the OpenAPI document needs a session, except health, login and logout | Verified by test |
| Role changes | Roles cannot be changed through the API (`AdminUserUpdate`: name and e-mail only); the user and role are re-read from the database on every request (`auth/deps.py`); disabling a user revokes all sessions (`users.set_active`) | No stale-privilege path found |
| Sessions and cookies | HttpOnly, SameSite=Strict; `Secure` enforced at start-up when `LEXFLOW_ENV=production` (`__main__.py`); idle (30 min) and absolute (12 h) expiry; lockout (`test_auth`) | Verified |
| Cross-case and cross-client access | `test_case_access`, `test_portal`, `test_search` (other cases never appear), `test_analysis_runs` (outsiders learn nothing) | Verified by tests |
| Clients and genuine judgments | Judgment routes are staff-only (`test_judgments_api`: clients 403, anonymous 401); clients have no upload route | Verified |
| Uploads | Type and content checks, size limits while streaming, server-chosen storage paths, control characters removed (`test_documents`) | Verified |
| Audit integrity | A row trigger rejects UPDATE and DELETE on `audit_events` (migration 0002, `test_audit_events_cannot_be_updated_or_deleted`) | Verified; see residual risk 3 |
| Database isolation | URL-name guards plus `current_database()` and marker checks on every destructive or import path; read-only transactions in the preview, verify, validate and evaluate scripts (Batches 1–3, tested) | Verified |
| Secrets | Scripts never print URLs or keys; error responses carry no values (`test_security`); the database URL reaches child processes only through the environment | Verified by tests and review |
| External AI data flow | D1: analysis only for sample cases unless `LEXFLOW_AI_ALLOW_CLIENT_DATA`; `e2e.py` forces the scripted provider; judgment passages enter analysis prompts (`analysis/evidence.py`) | See residual risk 1 |

**Residual risks** (not fixed; owner decisions or later work):
1. **Judgment text goes to the AI provider.** With a real provider, case
   analysis sends judgment passages, including the genuine public ones,
   and on non-sample cases client documents too, if D1 is lifted.
   - Sending public judgments to Google is not covered by any verified
     permission (the copyright question in the Batch 2 report).
   - On the Unpaid tier, content may be read by human reviewers.
   - **Mitigation:** keep D1, and confirm the billing tier before any
     real-model use.
2. **Session cookie not marked Secure** in development (`LEXFLOW_COOKIE_SECURE`
   is off by default). This is acceptable on `localhost` only;
   production refuses to start without it.
3. **The audit table's owner can bypass the trigger.** The application's
   database role owns the tables, so it could `TRUNCATE` or drop the
   trigger. A separate, less-privileged application role would close this.
   Not changed here: it is a deployment change.
4. **Prompt-injection detection is pattern-based.** Paraphrased injections
   pass detection; the other validation layers still apply (Batch 3).
5. **A document can state falsehoods as ordinary prose.** Validation proves
   provenance, not truth, and the lawyer sees every quote.

## Printed page labels: documented, not implemented

LexFlow's page references are **PDF pages**. One genuine judgment (*Lifestyle
Equities*, 2025 INSC 1190) prints page N − 1, because of an unnumbered cover
page. The validator warns about this (Batch 3).

A correct fix needs three changes:
- a new column on two section tables (a migration);
- label detection at extraction (PDF page labels, or printed markers),
  with re-extraction of existing documents;
- UI and analysis-reference changes.

That is not small or low-risk, so it stays a **known limitation**. The
interim guidance is that LexFlow page numbers are PDF page numbers, as
shown by a PDF viewer.

## Milestone 8: real-model evaluation

**Synthetic-only run done on 2026-10-27** (free tier; 21 runs; after bounded retries **15 complete, 6 incomplete** on Google server errors; 41 of 63 calls; results in `REAL_MODEL_APPROVAL_REQUEST.md`). Before that run it was **ready, not run**. The details are in
`docs/verification/batch3/REAL_MODEL_APPROVAL_REQUEST.md` (updated):
- the terms were re-verified (2026-04-28 version);
- the harness and its tests are in place;
- plan SHA-256 `9bbdb013…f207`;
- estimated USD 0.11 to 1.59.

**Blocker:** the API key's billing status (an active Cloud Billing account
means Paid) must be confirmed by the owner, and the run approved.

## Verification

| Command | Result |
|---|---|
| `pytest -q` | **1228 passed**, exit 0 (`logs/pytest.txt`) |
| ruff, format, mypy, OpenAPI check | exit 0 (`logs/static-checks.txt`) |
| `npm run check`, Playwright | not rerun: Batch 4 changed only `server/scripts/` and `server/tests/`, with no app or front-end code (the Batch 3 results stand: 212 passed and 47 passed) |
| Corpus (`verify_judgment_import.py`) | all 17 records match the manifest |

**Live `lexflow`:** 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
**Unchanged.** No model call was made. No commit, no push.
