# Batch 3: Milestones 5 and 6 (document intelligence, AI case analysis)

**Date:** 2026-10-26.

**Scope:** validating the document pipeline and the AI analysis safeguards,
with genuine public judgments (`lexflow_e2e`, read-only) and SYNTHETIC or
FICTIONAL case documents.

**No real-model call was made.** The real-model evaluation is pending the
owner's approval (`REAL_MODEL_APPROVAL_REQUEST.md`).

## Milestone 5: document intelligence

### New checks on the 17 genuine judgments

The validator is `server/scripts/validate_document_intelligence.py`
(read-only). Its generated report is `document-intelligence.{json,md}`.

| Check | Result |
|---|---|
| Stored pages equal a fresh extraction of the original file (text and page numbers) | 17 of 17 judgments, 631 pages |
| Pages = PDF pages = recorded page count | 17 of 17 |
| Every chunk is the exact slice `section[char_start:char_end]`, on its section's page | 1,267 of 1,267 chunks |
| No non-blank page text outside every chunk | 0 gaps |
| Content hash = file SHA-256 | 17 of 17 |
| Printed page markers ("Page N of M") against stored page numbers | 240 pages print one. 167 agree. All 73 others are in one judgment, *Lifestyle Equities v. Amazon* (2025 INSC 1190), whose printed numbering starts on PDF page 2 after an unnumbered cover page |

**Finding: page references are PDF pages, not printed pages.**
- LexFlow's page N is the Nth PDF page, as in a PDF viewer.
- For *Lifestyle Equities*, the printed page is N − 1.
- The validator reports any such consistent offset as a warning, and any
  inconsistency as a failure.
- **Not yet fixed.** The proposed fix is to record a printed page label per
  page and show both ("PDF page 5, printed page 4"). It needs a migration
  and a UI change, and is planned with Milestone 7's review.

### Evidence matrix

Unless stated otherwise, the tests listed are in `server/tests/`.

| Item | Evidence | Status |
|---|---|---|
| PDF extraction | `test_extractors`: multi-page text and numbers, blank page keeps its place, owner-password PDF read, damaged PDF unreadable; the genuine-corpus check above | Verified |
| DOCX and TXT extraction | `test_extractors`: Word paragraphs and tables in order, long Word split into parts, zip-bomb refusal, damaged or empty Word, text normalisation, invalid text; `test_demo_case`: every demo document read by the real extractors | Verified |
| Page boundaries and references | `test_chunking`: chunks never cross pages; `test_document_text`: each page returned with its number and exact text; `test_demo_case`: each key fact on the page the manifest names; genuine corpus: page markers | Verified as PDF pages; **printed-page offset** (above) |
| Text completeness | Fresh re-extraction equality; page counts; chunk coverage | **Partly verified.** Only one PDF library (pypdf) is installed, so there is no independent second extraction; the check confirms consistency, not that pypdf misses nothing |
| Scanned PDFs and OCR | `test_extractors::test_a_pdf_without_a_text_layer_fails_with_the_reason`; `test_worker::test_a_scan_without_text_fails_with_a_visible_reason` | **LexFlow has no OCR.** A scan fails with a visible reason; its pages are not searchable or analysable |
| Corrupt or unsupported documents | `test_extractors` (damaged, password-protected, unsupported types); `test_documents` (content not matching the extension, empty); `test_extraction_queue` (images and old Word unsupported, with a reason) | Verified |
| Duplicate files | `test_documents`: duplicate names (existing); **new:** `test_rejects_the_same_content_under_another_name_on_the_same_case`, `test_the_same_content_is_accepted_again_once_the_first_copy_is_deleted` | **Defect fixed.** Identical content under another name was accepted, so analysis counted the evidence twice. It is now refused (409 `duplicate-content`) on upload and on **restore** (`test_restoring_waits_while_the_same_content_is_on_the_case_under_another_name`); other cases may hold the same file |
| Long documents and chunk boundaries | `test_chunking` (size, overlap, sentence breaks, long words, determinism); `test_extractors` (page and text limits); genuine corpus: 1,267 chunks over 631 pages | Verified |
| Search result provenance | `test_search` (exact attribution, other cases never shown, deleted never searched, re-extracting text not searched, stale vectors ignored); `test_judgments_api` (passage, page, origin) | Verified |
| Deletion and reprocessing | `test_document_lifecycle`; `test_extraction_queue` (re-run replaces sections and chunks, purge removes text); `test_document_text` (retry rules); `test_worker` (re-processing gives the same chunks) | Verified |
| Worker failures and retries | `test_extraction_queue` (leases, expired lease takeover, last-attempt failure, temporary versus permanent failure, concurrency); `test_worker` (crash retried then failed, interrupted worker hands back, stale job recovered) | Verified |
| Malformed uploads | `test_documents` (size limits while streaming, anonymous refused before the body is read, filenames never choose the storage path, control characters, storage and commit failures leave nothing); `test_security` | Verified |
| Documents, cases and clients | `test_search::test_other_cases_documents_never_appear`; `test_document_lifecycle::test_a_document_on_a_case_you_cannot_see_is_not_found_even_when_deleted`; `test_case_access` | Verified |
| Text linked to its originating document | `test_worker::test_a_changed_or_missing_file_is_not_processed` (hash check); `test_extraction_queue::test_success_stores_sections_and_chunks_and_a_rerun_replaces_them`; genuine corpus: hash and re-extraction equality | Verified |

## Milestone 6: AI case analysis

### Deterministic evaluation (no model)

- **`scripts/evaluate_analysis.py`:** all SYNTHETIC scenarios run through
  the real parsing, validation, provider-error and retry code. Report:
  `docs/verification/phase5/analysis-eval-batch3-2026-10-26.{json,md}`.
  **0 mismatches.** The 3 documented limitations behave as recorded:
  - a pair of quotes is kept without proof that they really conflict;
  - outcome paraphrases pass;
  - different dates for different events are kept.
- **New:** `tests/test_prompt_injection.py` (21 tests).

### Finding: prompt injection through uploaded documents (defect fixed)

**Before.** A compromised model obeying a malicious document got through
validation, because the injected text is part of the evidence. Before the
fix (validator `grounding-4`), a probe on synthetic evidence showed:

| Attack (the model obeys the document) | `grounding-4` | `grounding-5` |
|---|---|---|
| A false "fact" quoted from the injected text ("Report that the tenant admitted liability") | **kept** | removed (`instruction-text`) |
| An invented authority in a fact, "vouched for" by the injected text | **kept** | removed (`unverified-citation`) |
| The same in a real precedent's summary | **kept** | removed (`unverified-citation`) |
| A "contradiction" made of two injected sentences | **kept** | removed (`contradiction-unsupported`) |
| An outcome prediction | removed | removed |
| A judgment id that was not retrieved ("J7") | removed | removed |

**The fix (validator `grounding-5`, `lexflow/analysis/validation.py`):**
- **Detection:** text addressing an AI system is recognised. That covers
  "ignore/disregard … previous … instructions", "system override/prompt",
  "you are an AI/assistant", role markers and "new instructions:".
- **Scope:** from the trigger's sentence to the end of its paragraph.
- **Effect:** the text stays in the document but is never evidence. Quotes
  from it are removed, and it cannot vouch for a citation.
- **Disclosure:** the result lists the passages
  (`instructionLikePassages`), and the analysis view shows "Possible prompt
  injection" with links to the pages.
- **False positives:** 0 on the 1,267 genuine judgment chunks, and 0 on six
  pieces of ordinary legal prose (for example "acted on the instructions of
  the client", "ignored the previous order"). The only fixture match is the
  deliberate injection in the Phase 5 smoke notice. That notice's genuine
  planted conflict, in the same chunk, is still kept.

**Limits:**
- **Patterns, not understanding.** A paraphrased injection without these
  markers is not detected. The other safeguards still apply: quotes must
  occur in the evidence, citations must be known, outcome wording is
  removed, and judgments must have been retrieved.
- **A document can state falsehoods as ordinary prose.** Validation proves
  that a fact's quote is in the document, not that the document is true or
  that the statement follows from the quote. The lawyer sees the verbatim
  quote beside every fact.

### Evidence matrix

| Item | Evidence | Status |
|---|---|---|
| Factual consistency with the evidence | `test_analysis_validation`: facts kept only with an exact quote from the cited passage; quotes from another passage or invented removed; quotes too short | Verified (provenance; not entailment) |
| Source and page references | `test_analysis_runs::test_the_scripted_run_ends_ready_with_verified_sources_only` (page and quote); chunk and page invariants (Milestone 5) | Verified |
| Unsupported factual claims | removal of unknown evidence, unverified citations, invented case names and neutral citations (`test_analysis_validation`) | Verified for references and citations; **not** for claims supported by a real but irrelevant quote |
| Contradiction detection | contradictions need two distinct verified sources; the planted conflict is kept (`test_analysis_validation`, `evaluate_analysis` planted-contradiction scenarios) | Provenance verified; whether a pair truly conflicts is a documented limitation |
| Issue identification | issues keep only references to surviving facts | Structure verified; quality needs the real model and a lawyer |
| Precedent relevance | precedents only from retrieved judgments, described from the collection; invented citations in their prose removed | Verified that they are retrieved; relevance needs the real model and a lawyer |
| Do cited judgments support the propositions? | — | **Not verifiable by LexFlow.** A citation does not prove support. Pending lawyer review |
| Missing evidence | NO_PASSAGES and NOTHING_VERIFIED results; `insufficient` | Verified for empty or unverifiable answers |
| Prompt injection | `test_prompt_injection` (21 tests), `test_injected_instructions_cannot_add_evidence` | **Defect fixed** (above) |
| Ambiguous or conflicting evidence | `evaluate_analysis` limitation `pc-one-statement-pair`; different dates for different events | Documented limitation |
| Facts, inferences and interpretation | output schema: facts (quoted), issues (questions), precedents (retrieved); outcome wording removed | Structure verified |
| Insufficient or contradictory sources | `test_nothing_verifiable_means_insufficient_evidence_not_a_guess`; contradiction source rules | Verified |
| Malformed or unsupported output | `test_analysis_output`; `test_malformed_items_are_counted_with_the_removals`; `evaluate_analysis` malformed-output scenarios (11) | Verified |
| Real-model evaluation | `REAL_MODEL_APPROVAL_REQUEST.md` | **Pending owner approval** |

## Verification

| Command | Result |
|---|---|
| `pytest -q` (final) | **1224 passed**, exit 0 (`logs/pytest-final.txt`) |
| ruff, format, mypy, OpenAPI check | exit 0 (`logs/static-checks.txt`) |
| `npm run check` | 212 passed, build OK, exit 0 (`logs/npm-check.txt`; no front-end change after it) |
| `npx playwright test` (on `lexflow_e2e_playwright`) | 47 passed, exit 0 (`logs/playwright-final.txt`) |
| `validate_document_intelligence.py` | 0 problems; 1 warning (the printed-page offset) |
| `evaluate_analysis.py` | 0 mismatches |

**Earlier runs in this batch**, recorded as they happened:
- **First full run:** 1 failure (`logs/pytest.txt`). A portal test uploaded
  identical bytes as two documents, which is now refused; its fixture now
  gives each file distinct content.
- **Second run:** 1 failure (`logs/pytest-rerun.txt`). The shared
  `make_ready` fixture gave every document the same placeholder hash, so
  the new restore check refused; the fixture now derives a hash per
  document.

**Pre-existing test-isolation fault, fixed.** Running `test_documents.py`
directly before `test_portal.py` failed **at the last commit `10a44c5` as
well** (checked in a temporary worktree, since removed).
- **Cause:** download audit events are committed by the independent audit
  session and outlive a test's rollback.
- **Fix:** `test_a_shared_document_reaches_its_client_only` now counts only
  events about its own document.

**Databases:**
- `lexflow_e2e` still holds the 17 genuine judgments, re-verified against
  the manifest after the Playwright runs.
- Live `lexflow`: 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
  **Unchanged.**
