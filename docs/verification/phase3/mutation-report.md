# Phase 3 mutation checks

Commit `c12d248`; run 2026-10-20 03:28 UTC; script `docs/verification/phase3/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests, and restores the file byte-for-byte (checked after every row, and `git status` of every target file checked clean at the end). **Caught** = the tests failed with the guard removed.

**Result: 14 of 14 caught.**

| ID | Guard | File | Tests run | Exit | Result |
|---|---|---|---|---|---|
| M4-1 | text is served only once it is ready | `server/lexflow/services/document_text.py` | `tests/test_document_text.py` | 1 | caught |
| M4-2 | a retry needs permission to add documents | `server/lexflow/api/documents.py` | `tests/test_document_text.py tests/test_access_required.py tests/test_portal.py` | 1 | caught |
| M4-3 | reading text is audited | `server/lexflow/api/documents.py` | `tests/test_document_text.py` | 1 | caught |
| M4-4 | no retry while already queued or processing | `server/lexflow/services/document_text.py` | `tests/test_document_text.py` | 1 | caught |
| M4-5 | Try again offered only to those who may upload | `src/components/workspace/DocumentsTab.tsx` | `src/pages/documentText.test.tsx` | 1 | caught |
| M4-6 | View text offered only when the text is ready | `src/components/workspace/DocumentsTab.tsx` | `src/pages/documentText.test.tsx src/pages/documentProcessing.test.tsx` | 1 | caught |
| M5-1 | local embeddings are refused | `server/lexflow/embeddings.py` | `tests/test_embeddings.py` | 1 | caught |
| M5-2 | the worker checks embeddings before claiming a job | `server/lexflow/worker.py` | `tests/test_embeddings.py` | 1 | caught |
| M6-1 | backfill leaves existing jobs alone | `server/lexflow/cli/documents.py` | `tests/test_cli_documents.py` | 1 | caught |
| M6-2 | backfill skips records without a stored file | `server/lexflow/cli/documents.py` | `tests/test_cli_documents.py` | 1 | caught |
| M6-3 | backfill previews before changing anything | `server/lexflow/cli/documents.py` | `tests/test_cli_documents.py` | 1 | caught |
| M6-4 | no retry for records without a stored file | `server/lexflow/services/document_text.py` | `tests/test_document_text.py` | 1 | caught |
| M6-5 | never-queued files are explained honestly | `server/lexflow/services/document_text.py` | `tests/test_document_text.py` | 1 | caught |
| M6-6 | Extract text offered only for stored files | `src/components/workspace/DocumentsTab.tsx` | `src/pages/documentText.test.tsx` | 1 | caught |

## Failing tests per check

- **M4-1**: `FAILED tests/test_document_text.py::test_text_is_not_available_until_it_is_ready_and_says_why`
- **M4-2**: `FAILED tests/test_document_text.py::test_no_retry_on_an_archived_case_or_for_a_deleted_document`
- **M4-3**: `FAILED tests/test_document_text.py::test_reading_text_is_audited - sqlalchemy...`
- **M4-4**: `FAILED tests/test_document_text.py::test_retries_that_cannot_help_are_refused`
- **M4-5**: `× retrying a failed extraction > is not offered on an archived case 121ms`; `FAIL  src/pages/documentText.test.tsx > retrying a failed extraction > is not offered on an archived case`
- **M4-6**: `× retrying a failed extraction > queues the document again 3112ms`; `FAIL  src/pages/documentText.test.tsx > retrying a failed extraction > queues the document again`
- **M5-1**: `FAILED tests/test_embeddings.py::test_local_embeddings_are_refused_with_the_reason`; `FAILED tests/test_embeddings.py::test_the_worker_takes_no_job_when_embeddings_cannot_run`; `FAILED tests/test_embeddings.py::test_the_worker_command_says_why_it_will_not_start`; `FAILED tests/test_embeddings.py::test_status_shows_that_local_embeddings_would_be_refused`
- **M5-2**: `FAILED tests/test_embeddings.py::test_the_worker_takes_no_job_when_embeddings_cannot_run`; `FAILED tests/test_embeddings.py::test_the_worker_command_says_why_it_will_not_start`
- **M6-1**: `FAILED tests/test_cli_documents.py::test_queue_extraction_queues_only_files_never_queued`
- **M6-2**: `FAILED tests/test_cli_documents.py::test_queue_extraction_previews_first - As...`; `FAILED tests/test_cli_documents.py::test_queue_extraction_queues_only_files_never_queued`; `FAILED tests/test_cli_documents.py::test_queue_extraction_marks_other_file_types_unsupported`; `FAILED tests/test_cli_documents.py::test_sample_records_without_files_are_never_queued`
- **M6-3**: `FAILED tests/test_cli_documents.py::test_queue_extraction_previews_first - as...`
- **M6-4**: `FAILED tests/test_document_text.py::test_retries_that_cannot_help_are_refused`
- **M6-5**: `FAILED tests/test_document_text.py::test_files_uploaded_before_extraction_existed_can_be_queued`
- **M6-6**: `× retrying a failed extraction > offers to extract files stored before extraction existed 152ms`; `FAIL  src/pages/documentText.test.tsx > retrying a failed extraction > offers to extract files stored before extraction existed`
