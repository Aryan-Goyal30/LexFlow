# 0018 — Judgment collection: operator imports with provenance, staff-wide search

Status: Accepted (Phase 4, 2026-10-20)

## Context

Phase 4 needs a collection of past judgments that lawyers can search and
browse, with each result traceable to its source. The brief requires a
curated set from public sources whose terms of use are checked, not assumed.
No source had been approved when Phase 4 was built, and LexFlow must never
present invented judgments as real ones.

## Decision

- **Import, never crawl.** Judgments enter only through
  `python -m lexflow.cli.judgments import <manifest.json>`: files the
  operator supplies plus a manifest (`lexflow-judgments/1`) naming the source
  and its **terms-of-use record** (where, when, by whom, what they permit).
  Strict validation; `https` addresses without credentials; files must stay
  inside the manifest's folder; preview first, `--confirm N` to apply; each
  judgment, its text and chunks are stored in one transaction. LexFlow keeps
  the extracted text, not the file; the source URL leads to the original.
- **Stable identity and honest metadata.** Id = uuid5 of
  `<source key>/<source's own id>`. Citation, date, bench and practice areas
  are stored only when supplied. Duplicates (same file, same citation, same id
  with new content) are reported; changed judgments are replaced only with
  `--update`.
- **Synthetic data is fenced off.** Test sources are marked synthetic, must
  use reserved `.invalid` addresses, are refused unless `--allow-synthetic`
  is given and the database name contains "test" or "e2e", and are labelled
  in every screen. The live collection stays empty until a real source is
  approved.
- **Search reuses Phase 3.** Page-aware chunks; keyword search on a stored
  `tsvector` with a GIN index; semantic search with the Phase 3 local model
  and pgvector (exact cosine, per judgment best passage); hybrid by
  reciprocal-rank fusion. At most 100 judgments ranked per query, then paged;
  deterministic tie-breaks. Embeddings stay off by default; judgments are
  embedded only by the explicit `index` command.
- **Access.** Judgments are firm-wide reference material: every staff role
  may browse and search; Client accounts never reach them; only the operator
  imports, indexes or removes. Searches are audited without their text.
- **Evaluation** is reproducible (`scripts/evaluate_judgment_search.py`,
  versioned sets recording their corpus hash) and reports Recall@K,
  Precision@K and MRR per mode and query kind.

## Consequences

- Until an approved source is imported, the Research tab and Precedent
  Library show an honest empty state on the live system.
- Real search quality is unmeasured: the shipped evaluation set is synthetic.
  A lawyer-labelled set on a licensed corpus is required before any claim.
- Exact semantic search scans every judgment vector; adequate for a curated
  set of hundreds of judgments, an approximate (HNSW) index will be needed for
  much larger collections.
- Withdrawing a source's licence is handled by
  `lexflow.cli.judgments remove --source KEY`.
