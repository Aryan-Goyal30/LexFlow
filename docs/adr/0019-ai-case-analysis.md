# 0019 — AI case analysis: Gemini behind the server, evidence ids, validation before display

Status: Accepted (Phase 5, 2026-10-20)

## Context

The brief's Phase 5 asks for AI case analysis: facts with their source
document and page, legal issues, precedent comparisons, contradictions and
judgment summaries, validated before they are shown, every claim linked to
its source, decision support only. The owner approved five decisions
(`docs/PHASE5_PLAN.md` §9): synthetic or sample cases only for now (D1);
Google's Gemini API with a configurable model and a key kept in
`server/.env` (D2); Google's official `google-genai` SDK (D3); only the
Administrator and the case's advocates may start a run, archived cases
refused, every read authorised (D4); the feature works without judgments and
says so (D5).

## Decision

- **The server talks to the model; the browser never does.** The key is a
  `SecretStr` read only when the worker builds the SDK client. It is never
  logged, audited, returned, put in OpenAPI or shown. The front end's
  `AiService` is an HTTP client of LexFlow's own API.
- **Runs are queued and processed by the worker** (`analysis_runs`, migration
  0011): lease, `SKIP LOCKED`, retries with a pause for busy or unreachable
  providers, one waiting or running run per case (partial unique index),
  per-person hourly limit. The provider is called outside any database
  transaction; a result is stored only while the worker still holds the run.
- **Evidence ids, not free-form citations.** The worker assembles the
  evidence (selected, live, extracted documents of the case: `D1…`; judgment
  passages from keyword retrieval: `J1…`; case context as uncitable
  background) within limits, and records references and content hashes, not
  text. The prompt (versioned, `case-analysis-v1`) fences the data with a
  content-derived marker and asks for a fixed JSON shape.
- **Validation decides what is shown.** The answer is parsed defensively;
  each fact needs a quote of at least 15 characters found (after Unicode and
  whitespace normalisation) in the one `D` passage it cites; a precedent must
  cite a `J` passage retrieved for the run, and its title, court and citation
  come from the collection; a contradiction needs two verified sources;
  issues keep only surviving facts; invented law-report citations and any
  outcome assessment are removed; every removal is counted with its reason.
  With nothing verifiable the result states insufficient evidence. Raw model
  output is not stored.
- **Honest limits.** Validation proves provenance, not legal correctness;
  the disclaimer says so with every result. No relevance percentage and no
  outcome assessment exist in the contract.
- **Gates.** Analysis is off by default (`LEXFLOW_AI_PROVIDER=disabled`).
  Missing key, model or migration → "unavailable" with the reason; the API
  and worker keep running. Only sample cases may be analysed until
  `LEXFLOW_AI_ALLOW_CLIENT_DATA=true` (checked by the API and again by the
  worker). The user must confirm, per run, that the selected text is sent to
  the named provider.
- **Testing without Google.** Tests use a fake SDK client or a scripted
  provider; building a real client fails in every test. The e2e harness uses
  the scripted provider (refused by the settings outside test and e2e
  databases), clearly labelled "not AI".

## Consequences

- Case text leaves the computer when a permitted user starts a run with
  Gemini configured. Production use with real client material needs a
  separate privacy, confidentiality and provider-terms review; a paid
  subscription alone does not settle it.
- The model name, its structured-output support and its price must be
  checked by the owner against Google's documentation; none is assumed.
- With the live judgment collection empty, results say that no precedents
  were available.
- A statement backed by a verified quote can still misread it: the lawyer
  verifies every point (Phase 6 adds per-item review).
- Migration 0011 must be applied to the live database (owner-gated) before
  analysis can run there.
