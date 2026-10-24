# LexFlow — instructions for Claude Code sessions

LexFlow is a local legal case management system: React and TypeScript in
`src/`; FastAPI, SQLAlchemy and Alembic in `server/`; PostgreSQL 17 with
pgvector in Docker (`server/compose.yaml`). Development follows
`docs/DEVELOPMENT_BRIEF.md` phase by phase, with an execution log and a
checkpoint per phase.

## Before changing anything

1. Read the current phase plan (`docs/PHASE6_PLAN.md`), its checkpoint
   (`docs/verification/phase6/checkpoint.json`) and the newest entries of
   its execution log (`docs/PHASE6_EXECUTION_LOG.md`). Phase 6 is closed;
   Phase 7 (outcome assessment) is gated and starts only on the owner's
   instruction, with its own plan, log and checkpoint.
2. Check `git status`, the branch, HEAD and the diffs. Compare them with the
   checkpoint, and never discard existing changes to make them match.
3. Verify the protected brief: `docs/DEVELOPMENT_BRIEF.md` SHA-256 must be
   `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`.
   Never modify that file.
4. Continue from the checkpoint's `next_action`. Do not repeat completed
   work, and inspect the real state before retrying any migration or import.

Resume instruction (enough on its own):

> Resume LexFlow Phase 6 from the latest verified checkpoint. Read CLAUDE.md, the Phase 6 plan, checkpoint and execution log; inspect Git state and the protected-file hash; reconcile actual repository state; then continue from the first incomplete task. Do not repeat completed work or discard existing changes.

## Rules that always apply

- **Never** push, deploy, change remotes or rewrite history. Commit only at
  verified milestones, with the phase's agreed message.
- **Never** make paid or real LLM calls. Tests use fakes, and the e2e app
  uses the scripted provider.
- **Never** print `.env` contents, keys, tokens or passwords.
- **Never** run tests, migrations or imports against the live database
  `lexflow`. The test suites use `lexflow_test`; e2e uses `lexflow_e2e`.
  Both are recreated by the project's own setup, and the URL guards refuse
  `dbname`/`service` parameters.
- Do not import, delete or bulk-change application records. Never treat
  synthetic judgments as real law.
- Logs are append-only. Record actual commands, exit codes and counts, and
  never present a historical result as fresh.
- Update the checkpoint atomically with
  `server\.venv\Scripts\python docs/verification/phase6/update_checkpoint.py PATCH.json`.
  The log must end with a `Checkpoint:` line that agrees with it.

## Useful commands

From `server/`:
- `.venv\Scripts\python -m pytest -q`
- `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .`
- `.venv\Scripts\mypy`
- `.venv\Scripts\python scripts/export_openapi.py --check`

From the repository root:
- `npm run check`
- `npm run api:types` (after an API change)
- `npx playwright test`
