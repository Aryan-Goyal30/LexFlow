# 0006 — Local disk document storage behind an interface

Status: Accepted (Phase 1)

## Context

Uploaded case papers must survive restarts. Cloud object storage would add
accounts, costs and network exposure that Phase 1 does not need, but the choice
should be easy to change later.

## Decision

- A `Storage` protocol (`put`, `open`, `delete`) with one implementation,
  `LocalDiskStorage`, rooted at `LEXFLOW_UPLOAD_DIR` (default
  `server/var/uploads`, git-ignored).
- Files are stored under a **random key** (`uuid4().hex`, sharded by its first
  two characters). The uploaded name is only ever data in the database, never
  part of a path. Names are cleaned (path parts, control and formatting
  characters removed, NFC, at most 255 characters).
- Uploads stream to a staging file while counting bytes; the 25 MB limit is
  enforced during streaming by middleware (413), not after buffering.
- The server checks the extension against an allow-list **and the contents**
  (magic bytes for PDF, images and legacy Word; the ZIP structure of `.docx`;
  valid UTF-8 text without NUL bytes for `.txt`), rejects empty files and
  duplicate names (case-insensitive, also enforced by a unique index), and
  records size, content type and SHA-256.
- Order of operations keeps the database and disk consistent: insert the row,
  move the file into place, commit; if the move fails the row is rolled back,
  if the commit fails the file is deleted. Deleting commits first, then removes
  the file.
- Downloads stream with `X-Content-Type-Options: nosniff`, `Cache-Control:
  no-store`, an RFC 5987 `filename*`, `inline` only for PDF, text and images,
  and a sandboxing `Content-Security-Policy` for inline non-PDF files.

## Consequences

- No encryption at rest, virus scanning, backups or retention rules yet; the
  README lists these as limitations.
- A future S3-style store only needs another `Storage` implementation.
