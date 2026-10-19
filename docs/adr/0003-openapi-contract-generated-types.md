# 0003 — OpenAPI as the contract; generated TypeScript types; drift checks

Status: Accepted (Phase 1)

## Context

The front end and the API are written in different languages. Hand-written
TypeScript copies of the API's shapes would drift silently.

## Decision

- The server's Pydantic models are the single source of truth. A post-processing
  step (`server/lexflow/openapi.py`) makes the document honest: error responses
  are declared as `application/problem+json` with the real Problem schema, and
  impossible 422s are removed.
- `server/scripts/export_openapi.py` writes `server/openapi.json`;
  `scripts/api-types.mjs` runs `openapi-typescript` to generate
  `src/services/api/schema.gen.ts`. Both generated files are committed.
- `src/types/index.ts` gives the generated types the app's names (`Case`,
  `CaseSummary`, `CaseDocument`, …), so components don't import generated paths.
- CI fails if either generated file is stale (`export_openapi.py --check`,
  `npm run api:check`).

## Consequences

- Changing the API is three steps (server, export, generate) and the type
  checker then lists every front-end site that must change.
- Field names are camelCase on the wire (Pydantic aliases), snake_case in
  Python.
