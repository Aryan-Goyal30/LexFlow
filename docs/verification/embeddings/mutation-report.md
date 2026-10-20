# Embeddings mutation checks

Commit `8eda562`; run 2026-10-20 04:45 UTC; script `docs/verification/embeddings/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests, and restores the file byte-for-byte (checked after every row, and `git status` of every target file checked clean at the end). **Caught** = the tests failed with the guard removed.

**Result: 16 of 16 caught.**

| ID | Guard | File | Tests run | Exit | Result |
|---|---|---|---|---|---|
| S-1 | deleted documents are never searched | `server/lexflow/services/retrieval.py` | `tests/test_search.py` | 1 | caught |
| S-2 | a search stays inside its case | `server/lexflow/services/retrieval.py` | `tests/test_search.py` | 1 | caught |
| S-3 | a vector of old text is never used | `server/lexflow/services/retrieval.py` | `tests/test_search.py` | 1 | caught |
| S-4 | vectors of another model are never compared | `server/lexflow/services/retrieval.py` | `tests/test_search.py` | 1 | caught |
| S-5 | semantic search refuses (409) when it cannot run | `server/lexflow/api/search.py` | `tests/test_search.py` | 1 | caught |
| S-6 | each search is audited | `server/lexflow/api/search.py` | `tests/test_search.py` | 1 | caught |
| I-1 | current vectors are not embedded again | `server/lexflow/services/indexing.py` | `tests/test_indexing.py` | 1 | caught |
| I-2 | finished batches are kept after a failure | `server/lexflow/services/indexing.py` | `tests/test_indexing.py` | 1 | caught |
| I-3 | a document locked by another worker is skipped | `server/lexflow/services/indexing.py` | `tests/test_indexing.py` | 1 | caught |
| I-4 | text extracted again during indexing discards the result | `server/lexflow/services/indexing.py` | `tests/test_indexing.py` | 1 | caught |
| I-5 | without embeddings, extracted text is not queued for indexing | `server/lexflow/worker.py` | `tests/test_worker.py` | 1 | caught |
| M-1 | missing or damaged model files are refused | `server/lexflow/embeddings.py` | `tests/test_embeddings.py` | 1 | caught |
| M-2 | a download that does not match its SHA-256 is refused | `server/lexflow/cli/models.py` | `tests/test_embeddings.py` | 1 | caught |
| M-3 | download previews before fetching | `server/lexflow/cli/models.py` | `tests/test_embeddings.py` | 1 | caught |
| M-4 | queue-indexing leaves current vectors alone | `server/lexflow/cli/models.py` | `tests/test_embeddings.py` | 1 | caught |
| M-5 | queue-indexing previews before changing anything | `server/lexflow/cli/models.py` | `tests/test_embeddings.py` | 1 | caught |

## Failing tests per check

- **S-1**: `FAILED tests/test_search.py::test_deleted_documents_are_never_searched - Asse...`
- **S-2**: `FAILED tests/test_search.py::test_other_cases_documents_never_appear - Assert...`
- **S-3**: `FAILED tests/test_search.py::test_a_vector_of_old_text_is_not_used - assert F...`
- **S-4**: `FAILED tests/test_search.py::test_vectors_of_another_model_are_never_compared`
- **S-5**: `FAILED tests/test_search.py::test_semantic_search_says_why_it_is_unavailable`
- **S-6**: `FAILED tests/test_search.py::test_each_search_is_audited_without_the_query - ...`
- **I-1**: `FAILED tests/test_indexing.py::test_indexing_again_embeds_nothing_twice - Ass...`; `FAILED tests/test_indexing.py::test_a_failure_keeps_finished_batches_and_a_retry_completes`; `FAILED tests/test_indexing.py::test_a_changed_chunk_is_embedded_again - Asser...`
- **I-2**: `FAILED tests/test_indexing.py::test_a_failure_keeps_finished_batches_and_a_retry_completes`
- **I-3**: `FAILED tests/test_indexing.py::test_a_document_locked_by_another_worker_is_skipped`
- **I-4**: `FAILED tests/test_indexing.py::test_text_extracted_again_during_indexing_discards_the_result`
- **I-5**: `FAILED tests/test_worker.py::test_a_multi_page_pdf_yields_page_numbered_text_and_chunks`
- **M-1**: `FAILED tests/test_embeddings.py::test_local_embeddings_need_the_downloaded_model`; `FAILED tests/test_embeddings.py::test_the_worker_takes_no_job_when_the_model_is_missing`; `FAILED tests/test_embeddings.py::test_the_worker_command_says_why_it_will_not_start`
- **M-2**: `FAILED tests/test_embeddings.py::test_a_download_that_does_not_match_is_refused_and_removed`
- **M-3**: `FAILED tests/test_embeddings.py::test_download_previews_first_and_fetches_nothing`
- **M-4**: `FAILED tests/test_embeddings.py::test_queue_indexing_previews_then_queues_what_lacks_current_vectors`
- **M-5**: `FAILED tests/test_embeddings.py::test_queue_indexing_previews_then_queues_what_lacks_current_vectors`
