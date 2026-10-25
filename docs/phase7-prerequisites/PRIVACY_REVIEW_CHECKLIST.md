# Privacy, confidentiality and provider-terms review (D1): checklist

Status: **checklist only (2026-10-25). The review has not been done.**
- Until it is complete and signed off, LexFlow analyses only sample or
  synthetic cases: `LEXFLOW_AI_ALLOW_CLIENT_DATA=false` (Phase 5 plan §9,
  D1; register R6).
- No real case data was used to write this.
- The legal references are prompts for the reviewer, not conclusions. The
  reviewer confirms which laws, rules and versions apply.

**Reviewer:** __________ **Date:** __________ **LexFlow commit reviewed:** __________

Each item: ☐ open / ☑ done / ✗ not acceptable. "Today" describes the
current code (checked 2026-10-25, HEAD `0d6914c` plus the race test).

## A. Scope and legal frame

- ☐ Which uses are under review? Choose one or more:
  1. real client documents stored in LexFlow;
  2. sent to Gemini for analysis;
  3. used for evaluation;
  4. public judgments stored.
- ☐ Which laws, rules and duties apply? Candidates the reviewer should
  confirm or dismiss:
  - the Digital Personal Data Protection Act 2023 and its Rules (status and
    commencement dates);
  - the Bar Council of India Rules on an advocate's duty of confidentiality;
  - professional-communication privilege (Bharatiya Sakshya Adhiniyam 2023,
    formerly Evidence Act s. 126);
  - the Information Technology Act 2000 and its rules;
  - court orders on anonymity or sealed records;
  - client engagement terms.
- ☐ Who is the data fiduciary (the practice)? Which processors are involved
  (Google for Gemini; any host)?

## B. Data categories (tick what real use would involve)

- ☐ Client identity and contact details (`clients`, portal users)
- ☐ Opposing parties, witnesses and third parties named in documents
- ☐ Children, victims of sexual offences, or people under court-ordered
  anonymity
- ☐ Health, financial, criminal-record, caste or religion data inside
  documents
- ☐ Government identifiers (Aadhaar, PAN, passport) inside documents
- ☐ Privileged advice and communications; the lawyer's work product
  (reviewers' notes, edited findings, briefs)
- ☐ Staff data: users, sign-in sessions, audit trail
- ☐ Public judgments that name real people (if a source is approved; see
  `SOURCE_CANDIDATE_SCI_JUDGMENTS.md` §4)

## C. Access

- ☐ The role model is right for real matters:
  - Today: Administrator, advocates (lead and associate per case),
    paralegals, clients through the portal.
  - Reviewers' notes are hidden from paralegals.
  - Clients see only their own cases and cannot reach AI analysis or review.
- ☐ Who holds the Administrator role, and how is it controlled?
- ☐ Sign-in, sessions and lockout are adequate.
  - Today: idle timeout 30 minutes, absolute limit 12 hours (configurable),
    lockout after failed attempts.
- ☐ Is the audit trail enough to answer "who saw or changed what"?
  - Today it records actions with codes and counts, never document text or
    notes.
  - Are reads of documents audited to the needed degree?

## D. Storage and security

- ☐ Where does each copy live?
  - Today: PostgreSQL in Docker on this machine, published on `127.0.0.1`
    only (`server/compose.yaml`).
  - Uploaded files in `server/var/uploads`.
  - Extracted text, chunks and local embeddings in the database.
  - Dumps and base backups in `server/var/backups` (8 dumps and 2 base
    backups today).
  - Restore databases: `lexflow_pre0012_verify`, `lexflow_p3_restore`,
    `lexflow_restore_check`.
- ☐ Encryption at rest: disk encryption on this machine (BitLocker or
  equivalent)? Encrypted backups? Column encryption for notes (register R2:
  notes are stored unencrypted today)?
- ☐ Is the machine shared, and who has OS-level access?
- ☐ The secrets policy is adequate (keys only in `server/.env`, never
  logged).

## E. External transfers

- ☐ **Gemini (Google).** What is sent today:
  - the selected case documents' text chunks;
  - retrieved judgment passages;
  - the instructions.
  - The UI states this and asks for confirmation before every run.
  - Nothing else leaves the machine: search embeddings use a local model,
    and tests use fakes.
- ☐ Provider terms, read and recorded (URL, version, date, reader):
  - data use for training;
  - retention and logging of prompts and responses;
  - human review;
  - data location and transfer outside India;
  - the terms of the paid tier versus the free tier;
  - sub-processors;
  - breach notification.
  - D1 notes: "a paid subscription alone does not establish legal or
    contractual compliance".
- ☐ Is client consent or an engagement clause needed for AI processing? For
  cross-border transfer?
- ☐ Minimisation: is the selected-document scope enough, or is redaction
  needed before sending (names, identifiers)? Today there is no redaction.
- ☐ No other transfers. Confirm there is no telemetry or other external
  service.
  - Today no analytics service or telemetry exporter is configured in the
    code. `opentelemetry-api` is installed only as a FastAPI dependency,
    with no SDK or exporter.
  - Also check whether `huggingface-hub` contacts the network when the
    local embedding model in `server/var/models` is loaded.

## F. Retention and deletion

- ☐ Set a retention period per category (case files, analysis results,
  reviews and notes, audit, sessions, backups).
- ☐ Deletion today:
  - documents are soft-deleted (restorable) until an Administrator runs
    `python -m lexflow.cli.documents purge` (it previews first);
  - cases are archived, not deleted;
  - analysis runs and review history are kept by design (append-only
    history).

  Is that acceptable, and how is a client's erasure request handled?
- ☐ Backups and restore databases keep data after deletion. Set a rotation
  rule (register R3).
- ☐ Data held by Gemini after a run: governed by the provider terms in E.

## G. Risks of using real case documents (assess each)

- ☐ Confidential or privileged material leaves the practice's control (E).
- ☐ The model returns wrong or ungrounded findings and they are relied on.
  - Mitigations: validation, mandatory lawyer review (Phase 6), the
    decision-support label.
  - Pattern limits are known (Phase 5 M10).
- ☐ Injected instructions in documents. Validation removes such output, but
  live behaviour is unverified (register R7).
- ☐ Over-sharing inside the firm: wrong case membership, or exports (the
  DOCX brief) leaving the system.
- ☐ Loss or theft of the machine or the backups (D).
- ☐ Mixing synthetic and real data: SYNTHETIC labels on fixtures and demo
  judgments must stay visible.

## H. Sign-off

- ☐ Conditions for enabling `LEXFLOW_AI_ALLOW_CLIENT_DATA=true`, if any,
  written down.
- ☐ Decision recorded by the owner (date, scope, conditions, review date)
  in the Phase plan in force and in the register (R6).
