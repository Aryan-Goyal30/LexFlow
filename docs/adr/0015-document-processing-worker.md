# 0015 — Document text extraction in a separate, database-backed worker

Status: Accepted (Phase 3)

## Context

Uploaded court papers must become searchable text with page numbers, for
reading now and for retrieval and analysis later. Extraction is slow and
risky: parsers can hang or crash on damaged or hostile files, and a PDF can
claim thousands of pages. The API must stay responsive, and a failure must be
visible, never silent. LexFlow runs on one machine with PostgreSQL already in
place; adding a message broker would be one more service to run and secure.

## Decision

- **Queue in PostgreSQL.** Each stored file gets one row in
  `document_extractions`, created in the upload's transaction. Statuses:
  `queued`, `processing`, `ready`, `failed` (code and reason), `unsupported`.
  Workers claim jobs with `FOR UPDATE SKIP LOCKED` and a lease; several can
  run at once. A job whose worker stopped is taken over after the lease; one
  abandoned on its last attempt fails as "interrupted". Only the worker that
  still holds a job may store its result.
- **A separate process**, `python -m lexflow.worker`, not a thread in the API.
- **Each file is extracted in a child process** (spawned), killed at the time
  limit. Limits on pages, extracted text and unpacked `.docx` size; the stored
  file must match its upload SHA-256. Temporary problems (unreadable storage,
  a crashed extractor) are retried up to 3 times; time-outs and bad files are
  not.
- **Libraries:** pypdf (PDF text layer), python-docx (body paragraphs and
  tables), UTF-8 for text. **No OCR**: scans fail with "no text layer";
  images and `.doc` are `unsupported`.
- **Page-aware storage.** `document_sections`: one per PDF page with its page
  number, or ~20,000-character parts (no page number) for Word and text.
  `document_chunks`: at most 1,200 characters, about 200 overlapping, never
  across sections, with exact offsets (`text == section[start:end]`) and a
  SHA-256 each, so later citations can point to a page and a passage.
- **Access** follows the document's case: staff on the case read the text
  (audited per read, never logging the text); staff who may upload ask for a
  retry. Client accounts never receive extracted text. Deleted documents'
  text is hidden with them.
- **Existing files** (uploaded before migration 0008) are queued only by an
  explicit command (`lexflow.cli.documents queue-extraction`, preview first),
  or one at a time from the Documents tab.

## Consequences

- One more process to start (the e2e harness starts it too). Without it,
  documents stay "Waiting for text extraction", which the UI says plainly.
- Polling every 2 s costs a small query; no broker to install or secure.
- Extracted text is stored unencrypted in the database, like the files on disk.
- Word files have no page numbers; citations into them name a part instead.
- OCR, and text from headers, footers and comments, are not covered.
