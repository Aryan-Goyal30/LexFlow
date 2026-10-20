# Phase 4 mutation checks

Commit `5448ec0`; run 2026-10-20 08:03 UTC; script `docs/verification/phase4/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests, and restores the file byte-for-byte (checked after every row, and `git status` of every target file checked clean at the end). **Caught** = the tests failed with the guard removed.

**Result: 19 of 19 caught.**

| ID | Guard | File | Tests run | Exit | Result |
|---|---|---|---|---|---|
| I-1 | synthetic sources need --allow-synthetic | `server/lexflow/cli/judgments.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-2 | synthetic data never enters a non-test database | `server/lexflow/cli/judgments.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-3 | files cannot leave the manifest's folder | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-4 | addresses must be https | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-5 | synthetic sources use reserved .invalid addresses | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-6 | a file already in the collection is a duplicate | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-7 | a citation already in the collection is a duplicate | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-8 | a source cannot switch between real and synthetic | `server/lexflow/services/judgment_import.py` | `tests/test_judgment_import.py` | 1 | caught |
| I-9 | commands preview before changing anything | `server/lexflow/cli/judgments.py` | `tests/test_judgment_import.py` | 1 | caught |
| A-1 | only staff reach the collection | `server/lexflow/main.py` | `tests/test_judgments_api.py` | 1 | caught |
| A-2 | semantic search refuses (409) when it cannot run | `server/lexflow/api/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| A-3 | searches are audited | `server/lexflow/api/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| A-4 | queries are at most 300 characters | `server/lexflow/api/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| A-5 | search pages are bounded | `server/lexflow/api/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| R-1 | vectors of another model are never compared | `server/lexflow/services/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| R-2 | a vector of old text is never used | `server/lexflow/services/judgments.py` | `tests/test_judgments_api.py` | 1 | caught |
| U-1 | source links are https only | `src/components/research/Judgments.tsx` | `src/pages/research.test.tsx` | 1 | caught |
| U-2 | unavailable search modes cannot be chosen | `src/components/research/Judgments.tsx` | `src/pages/research.test.tsx` | 1 | caught |
| U-3 | results never outlive their query | `src/hooks/useJudgments.ts` | `src/pages/research.test.tsx` | 1 | caught |

## Failing tests per check

- **I-1**: `FAILED tests/test_judgment_import.py::test_synthetic_sources_need_the_explicit_flag`
- **I-2**: `FAILED tests/test_judgment_import.py::test_synthetic_sources_are_refused_outside_test_databases`
- **I-3**: `FAILED tests/test_judgment_import.py::test_bad_files_are_invalid[../../secret.txt-leaves the manifest's folder]`
- **I-4**: `FAILED tests/test_judgment_import.py::test_invalid_manifests_import_nothing[<lambda>-https://]`
- **I-5**: `FAILED tests/test_judgment_import.py::test_invalid_manifests_import_nothing[<lambda>-.invalid]`
- **I-6**: `FAILED tests/test_judgment_import.py::test_duplicates_are_reported_not_stored`
- **I-7**: `FAILED tests/test_judgment_import.py::test_duplicates_are_reported_not_stored`
- **I-8**: `FAILED tests/test_judgment_import.py::test_a_source_cannot_switch_between_real_and_synthetic`
- **I-9**: `FAILED tests/test_judgment_import.py::test_preview_lists_everything_and_changes_nothing`; `FAILED tests/test_judgment_import.py::test_duplicates_are_reported_not_stored`; `FAILED tests/test_judgment_import.py::test_indexing_needs_embeddings_and_previews`; `FAILED tests/test_judgment_import.py::test_removing_a_source_needs_the_previewed_count`
- **A-1**: `FAILED tests/test_judgments_api.py::test_clients_and_anonymous_callers_are_refused`
- **A-2**: `FAILED tests/test_judgments_api.py::test_semantic_and_hybrid_need_embeddings`
- **A-3**: `FAILED tests/test_judgments_api.py::test_judgment_searches_are_audited_without_the_query`
- **A-4**: `FAILED tests/test_judgments_api.py::test_invalid_search_requests_are_refused`
- **A-5**: `FAILED tests/test_judgments_api.py::test_pages_split_one_ranking_without_gaps_or_repeats`
- **R-1**: `FAILED tests/test_judgments_api.py::test_vectors_of_another_model_are_not_used`
- **R-2**: `FAILED tests/test_judgments_api.py::test_semantic_search_uses_current_vectors_only`
- **U-1**: `× Research tab > never links to a source address that is not https 236ms`; `FAIL  src/pages/research.test.tsx > Research tab > never links to a source address that is not https`
- **U-2**: `× Research tab > offers meaning-based search only when the server can do it 62ms`; `FAIL  src/pages/research.test.tsx > Research tab > offers meaning-based search only when the server can do it`
- **U-3**: `× Research tab > never shows the results of an earlier search as those of a new one 543ms`; `× Research tab > pages through many results 1342ms`; `FAIL  src/pages/research.test.tsx > Research tab > never shows the results of an earlier search as those of a new one`; `FAIL  src/pages/research.test.tsx > Research tab > pages through many results`
