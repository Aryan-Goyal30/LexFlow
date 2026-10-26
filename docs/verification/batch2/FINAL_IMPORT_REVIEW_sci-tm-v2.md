# Final import review: `sci-tm-v2` into `lexflow_e2e`

**Date:** 2026-10-25.

**Status:** prepared and checked. **Nothing has been imported.** The import
runs only after the owner approves this exact preview: manifest SHA-256
`4b3134b7b9de3d0740153c93463ef9cb7e4fae32b30a9eb8d9b24e48ac4cb3f3`
(`import-preview-sci-tm-v2.md`).

This is a technical preparation, **not legal advice and not a legal review**.

## 1. What changed since `sci-tm-v1`

- **The 3 background-only judgments** are added as separately identified
  **evaluation candidates**. Their relevance is to be judged against each
  query, never assumed. They carry no topic tag.
- **Every judgment's provenance now records:**
  - its role;
  - "Prepared by: Claude Code (AI assistant): automated technical selection
    and preparation; not a legal review";
  - "Legal review: not performed";
  - notes where the archive copy has editorial matter.
- **The source's terms record** now reads "Technical check only: Claude
  Code (AI assistant), 2026-10-25. No legal review yet." It no longer
  suggests a human legal reviewer.
- **The judgment page** shows the preparation, the legal-review status, the
  role, the notes and any change to the file.
- `sci-tm-v1` is kept unchanged for traceability. `sci-tm-v2` is a new
  folder built from the same verified downloads.

## 2. The four older-archive PDFs with a `HEADNOTE:` label

The text between the labels was measured in each file. Nothing was removed
or altered.

| Judgment | Editorial matter in the file | Where | Separable? |
|---|---|---|---|
| *Amritdhara Pharmacy v. Satyadeo Gupta* (1962) | Catchwords (`ACT:`, 140 characters) and a **headnote** (`HEADNOTE:`, 2,940 characters) | Pages 1–2, before `JUDGMENT:` | In text, yes: explicit labels mark where it starts and ends. In the PDF, no: it shares pages 1–2 with the judgment |
| *Parle Products v. J. P. & Co.* (1972) | Catchwords (157 characters) and a **headnote** (2,255 characters, with law-report page references such as "1294 F-H]") | Pages 1–2, before `JUDGMENT:` | As above |
| *Whirlpool Corporation v. Registrar of Trade Marks* (1998) | **None.** The `ACT:` and `HEADNOTE:` labels are empty | — | Nothing to separate |
| *Gujarat Bottling v. Coca Cola* (1995) | **None.** The labels are empty | — | Nothing to separate |

**Authorship.** Neither file says who wrote its headnote.
- **Pointing to the official report:**
  - The Parle headnote's style (marginal page-letter references) and its
    printed "1972 SCR (3) 289" citation suggest it comes from the Supreme
    Court Reports.
  - The e-SCR "About" page, in the saved evidence, calls SCR "the official
    publication of Supreme Court of India".
- **Not certain:**
  - The Amritdhara file prints only an AIR citation.
  - **Authorship is therefore not verified.**

**Is it covered by the permission?** On its wording, the sci.gov.in
copyright policy covers "the contents on this website". It excludes only
"material which is identified as being copyright of a third party".
- Neither headnote is identified as third-party material.
- Both are served by the Court's own host, inside the Court's file.

So the permission covers them **on its face**. Whether a headnote could
still belong to someone else is the unresolved question (section 3).

**Options per document:**

| Judgment | Options | Recommended |
|---|---|---|
| *Amritdhara* | **(a)** import unaltered, with the provenance note (shown on the judgment page) that pages 1–2 carry editorial matter not part of the judgment; **(b)** hold back until a lawyer confirms authorship; **(c)** remove the headnote: **not recommended**, as it alters the official document | **(a)**, local use only, not redistributed. Choose (b) if any doubt is unacceptable |
| *Parle Products* | As above | **(a)**, with the same proviso |
| *Whirlpool* | Import unaltered (no editorial text); a note records the empty labels | Import |
| *Gujarat Bottling* | Import unaltered; a note records the empty labels and the header's "POTTLING" spelling | Import |

**Known effect of (a) on search.** Passages from pages 1–2 of the two
judgments may include headnote text. A search hit there could show
editorial wording rather than the Court's. The note on the judgment page
says so. Marking such passages individually is a possible later
improvement; it is not built.

## 3. Terms: verified permissions, and unresolved questions

The live pages were **re-read on 2026-10-25**. The copyright policy and the
terms text are **identical** to the saved evidence.

**Verified (quoted from the official pages):**
1. **sci.gov.in copyright policy:** reproduction is permitted "duly &
   prominently acknowledging the source". It may not be used "in any
   misleading or objectionable context or derogatory manner". The
   permission does not extend to "material which is identified as being
   copyright of a third party". e-SCR has the same wording.
2. **Terms:** the documents are "for reference purposes only and the same
   do not constitute legal document"; in case of doubt, verify with the
   authorities.
3. **robots.txt:** `www.sci.gov.in` disallows only `/wp-admin/`. No terms
   page read addresses automated access.
4. **CAPTCHA:** it protects the Court's search pages only. The PDFs used
   were fetched at addresses on the Court's host that require none, as the
   Court's own "View Judgment" links do.

**Proposed use** (local research prototype):
- **Kept local:** PDFs stored on this computer, outside Git; never
  redistributed or published.
- **Processed locally:** text extracted and indexed for keyword search.
  Local embeddings come only if enabled; the model runs on this computer.
- **Shown to signed-in staff of the local app:**
  - passages, always with the attribution;
  - a link to the Court's copy;
  - the caution "for reference; check the official copy".
- **Not sent to any external service.** In `lexflow_e2e`, case analysis uses
  the scripted provider only, so judgment passages placed in analysis
  prompts stay on this computer.

**Unresolved (for the owner, ideally with a lawyer):**
1. Whether "reproduce" in the policy covers storing, extracting, indexing
   and showing passages in a local tool. The plain reading supports it, but
   it is not stated.
2. Authorship and ownership of the two headnotes (section 2).
3. The Copyright Act, s. 52(1)(q)(iv) (judgments are not infringed unless
   the court prohibits reproduction). It is still unverified against the
   official text (India Code timed out).
4. Whether fetching from direct links found by web search (rather than
   through the CAPTCHA-protected search) is acceptable to the Court. No
   stated rule forbids it; none permits it explicitly.
5. **Personal data (DPDP Act).**
   - Individuals named as parties: about 6 in the core corpus.
   - In *Asian Paints v. Ram Babu*, an individual was accused of cheating
     and copyright offences and acquitted by the High Court. This is a
     published, reportable judgment, but it attaches a criminal allegation
     to a named person. Excluding it is an option.
6. **Real AI models.** With `LEXFLOW_AI_PROVIDER=gemini`, case analysis
   would place judgment passages in prompts sent to Google. This is
   **not enabled** for `lexflow_e2e`. Any such run needs the owner's
   approval (Batch 4 gate).

## 4. The exact documents (full details in the preview)

- **17 documents:**
  - 14 core corpus (10 core, 4 related);
  - 3 evaluation candidates.
- **All new;** 0 duplicate, 0 invalid.
- **Every file extracts,** with no empty pages.
- **6 transformed:** the legacy archive's 4-byte length prefix is removed.
  - The original bytes are kept in `original/`.
  - Both SHA-256 values are in provenance.
  - Affected: *IPRS v. Sanjay Dalia*, *Whirlpool*, *Amritdhara*, *Milmet
    Oftho*, *Parle Products*, *Gujarat Bottling*.
- **The other 11 are byte-identical** to what the Court served.
- **Attribution (every judgment):** "Source: Supreme Court of India,
  sci.gov.in (judgment copy as published by the Court). Reproduced with
  acknowledgement under the website's copyright policy. For reference only;
  not a legal document."
- **Excluded:** the 23 off-topic downloads (tax, power, service and similar
  matters wrongly associated by web search). They are kept in staging and
  not imported.

## 5. Isolation: verified on 2026-10-25 (read-only)

- **Container:** one PostgreSQL container (`pgvector/pgvector:pg17-trixie`)
  on `127.0.0.1:5432`, volume `lexflow_pgdata`. No volume or container will
  be touched.
- **`DATABASE_URL`** names the live `lexflow`, with no URL parameters. The
  import never uses it.
- **`lexflow_e2e`:**
  - the only database carrying the marker `lexflow:isolated-demo:v1`;
  - at 0014;
  - holds 1 source (the synthetic fixtures): 13 judgments, 13 provenance
    rows, 1 import run;
  - no `sci-judgments` source.
- **Live `lexflow`:** 0012, no 0014 tables; 7 | 6 | 7 | 32 | 8 | 10 | 116 |
  2 | 3. Unchanged.
- **The import runs through `scripts/import_judgments_isolated.py`**, which
  refuses unless, in order:
  1. the manifest's SHA-256 is the approved one;
  2. the database has "e2e" as a name part and is not the `DATABASE_URL`
     database (no `dbname`/`service` parameters);
  3. the connection reports `lexflow_e2e` and the demo marker.

  It then runs the existing import CLI, which still requires
  `--confirm 17`. Tests: `tests/test_import_preview.py` (11).
- **Command, after approval:**

  ```
  .venv\Scripts\python scripts/import_judgments_isolated.py var/judgments/sci-tm-v2/manifest.json --expect-manifest-sha256 4b3134b7b9de3d0740153c93463ef9cb7e4fae32b30a9eb8d9b24e48ac4cb3f3 --database lexflow_e2e --confirm 17
  ```

- **Reversal:** `python -m lexflow.cli.judgments remove --source sci-judgments`,
  run against `lexflow_e2e` through the same identity checks.

**Important: Playwright resets `lexflow_e2e`.** Its global setup runs
`e2e.py prepare`, which drops and recreates the database. After the import:
- an ordinary Playwright run would delete the imported judgments;
- Playwright should therefore run with
  `LEXFLOW_E2E_DATABASE=<another name containing "e2e">`. Playwright passes
  its environment to `e2e.py`, so that throwaway database is created and
  reset instead. Creating that database needs the owner's agreement;
- otherwise the import must be repeated after each e2e run. It is
  reproducible from the manifest.

For this reason, Playwright was **not** run in this round.

## 6. Remaining caveats

- **Below target:** 14 core documents, below the 20–40 originally proposed.
  A first technical evaluation is possible, but results describe this small
  corpus only.
- **Evaluation labels:** no lawyer labels exist. Any evaluation before a
  lawyer labels queries uses developer-written or citation-proxy labels,
  reported as such.
- **The two headnotes** (section 2) and the **unresolved questions**
  (section 3).
