# Batch 2: ingestion, retrieval and evaluation tooling

**Status:** built and tested on invented data only. **No genuine judgment
has been downloaded or imported.** Importing waits for the owner's approval
of the source and the action (`SOURCE_AND_LICENSING_REPORT.md` section 6).

## 1. Ingestion

### Manifest format 2 (`lexflow-judgments/2`)

`server/lexflow/services/judgment_import.py` accepts format 1 unchanged,
and format 2 with these additions:

| Where | Field | Rule |
|---|---|---|
| `source` | `licence` | the licence as the source states it (optional) |
| `source` | `attribution` | the acknowledgement to show; **required for a real (non-synthetic) source** |
| top level | `dataset` | `name`, `publisher`, https `url`, `version`, `retrieved_on` (optional) |
| each judgment | `neutral_citation` | optional, 1–100 characters |
| each judgment | `provenance` | the source's own record fields: lower_snake_case keys, at most 30; `null` values are dropped, never stored as guesses |

A format-1 manifest that uses any of these is refused.

### Storage (migration 0014, additive)

- **`judgment_provenance`:** one row per judgment, written in the same
  transaction as the judgment. It holds the neutral citation, the source
  record (always including the file's own `file_sha256`), the dataset and
  the attribution.
- **`judgment_import_runs`:** one row per apply. It holds:
  - the manifest's format and SHA-256, the operator and the times;
  - planned counts by status, plus imported, updated and rejected;
  - every item that was not imported (duplicate, invalid, rejected), with
    its reason.

No existing table or column changes. An application at 0012 or 0013 keeps
working, and the importer skips both records when the tables are absent.

> **The live database `lexflow` is at 0012** and has not been migrated.
> Migrating it is a separate approval.

### The hand-picked-folder adapter

```
server\.venv\Scripts\python server/scripts/prepare_official_judgments.py FOLDER --checked-by "NAME"
```

It works offline: no network request and no database.
- **Input:** `FOLDER` holds the PDFs, downloaded by hand from the official
  portal, and a `selection.csv`.
- **Output:** `FOLDER/manifest.json` (format 2).

**`selection.csv` columns:**
- required: `file`, `title`, `court`, `source_url`, `selected_by`;
- optional: `decision_date` (YYYY-MM-DD), `year`, `citation`,
  `neutral_citation`, `bench`, `practice_areas` (separated by `;`),
  `selection_reason`.

A blank cell means unknown, and nothing is filled in.

**Checks** (every problem is listed, and no manifest is written):
- the file is in the folder, and really a PDF;
- no repeated files (by SHA-256) and no repeated ids;
- `source_url` is on the profile's official hosts;
- the importer's own validation passes.

**Ids:** `nc-<neutral citation>` when there is one, otherwise
`sha256-<first 16 hex digits>`.

**The `sci-escr` profile:**
- terms URL: the e-SCR copyright policy;
- `permitted_use`: quotes the policy as saved in
  `source-evidence/scr-footer-cp.html`;
- official hosts: `scr.sci.gov.in`, `sci.gov.in`, `www.sci.gov.in`;
- the attribution proposed in the report. The owner may replace it with
  `--attribution`.

**The `sci-judgments` profile** (Supreme Court judgments published on
sci.gov.in):
- terms URL: the website policies page;
- `permitted_use`: quotes its copyright policy and terms;
- official hosts: `api.sci.gov.in`, `main.sci.gov.in`, `www.sci.gov.in`,
  `sci.gov.in`.

**Optional retrieval columns:**
- `retrieved_from` (official host only);
- `retrieved_at` (UTC);
- `original_sha256`;
- `original_transform`. It is required when the imported file differs from
  the original. For example, the legacy archive's 4-byte length prefix is
  removed.

All four go into the judgment's provenance. Unknown values are left out of
the manifest.

**Dry run:**

```
.venv\Scripts\python scripts/preview_judgment_import.py MANIFEST --database lexflow_e2e --out PREVIEW.md
```

It shows the plan, each file's extracted pages and characters, the
attribution and any issues.
- **The database is named on the command line**, never taken from
  `DATABASE_URL`: it must be a test or e2e database, and not the
  configured (live) one.
- **Identity is checked:** the connection must report that name, and an e2e
  database must carry the demo marker.
- **No changes:** planning runs in a READ ONLY transaction that is rolled
  back.

Then, **only after approval**, and with `DATABASE_URL` naming the approved
evaluation or demo database:

```
python -m lexflow.cli.judgments import FOLDER/manifest.json            # preview
python -m lexflow.cli.judgments import FOLDER/manifest.json --confirm N
```

## 2. Retrieval

- **The `origin` filter:** `GET /api/judgments` and `/api/judgments/search`
  accept `origin=genuine|synthetic`. In the Precedent Library, the filter
  is shown only when the collection holds both kinds.
- **Labels:**
  - every judgment carries a badge: "Genuine judgment" or "Synthetic test
    data";
  - a genuine judgment's page says it was found by matching text, not by
    judging legal relevance, and should be checked against the official
    copy.
- **Provenance:** `GET /api/judgments/{id}` has a `provenance` block
  (attribution, neutral citation, dataset, source record). The judgment
  page shows the attribution, neutral citation, dataset and file SHA-256.
- **Keyword fallback (after the first evaluation):** keyword mode first
  requires every word. If no passage has them all, it ranks passages with
  any of the words, and reports `keywordMatch: "any"`. The Precedent
  Library then says so. Hybrid keeps every-word matches, because the
  fallback lowered hybrid ranking (`EVALUATION_REPORT.md`).
- **Evaluation:** `scripts/evaluate_genuine_retrieval.py`, with results and
  limitations in `EVALUATION_REPORT.md`.
- **Search methods are unchanged:** keyword (PostgreSQL full text), semantic
  (local embeddings, when enabled) and hybrid (reciprocal-rank fusion).
  Whether hybrid is better for genuine judgments is to be measured on the
  approved corpus. It is not assumed.

## 3. Evaluation framework

**Metrics**, in `server/lexflow/evaluation.py`:
- Recall@k, Precision@k and MRR (existing);
- **nDCG@k** on grades 0–3 (gain 2^g − 1, log2 discount, ideal over every
  graded judgment);
- the number of **unjudged** results in the top k;
- **Cohen's kappa** for two reviewers.

**Sets**, in `server/lexflow/relevance_sets.py`: one folder per set version,
as in `docs/phase7-prerequisites/ANNOTATION_GUIDE.md` section 8, plus
`set.json`.

| File | Content |
|---|---|
| `set.json` | `name`, `version`, `label_origin` (`lawyer`, `synthetic` or `citation-proxy`), `guide_version`, `reviewers` (pseudonymous), optional `corpus` (`source_key`, `manifest_sha256`) |
| `queries.jsonl` | `query_id`, `area`, `summary`, optional `cutoff_date`, `source_key`, `cnr`, `guide_version` |
| `labels.jsonl` | `query_id`, `judgment` (`source_key` plus `id` or `cnr`), `grade` 0–3, `reason` and `passage` (required for grades 2–3), `reviewer`, `labelled_on`, optional `minutes_spent` |

**Rules:**
- Relevant means grade 2 or 3.
- A `lawyer` set must name its reviewers, and every label must be by one of
  them, or `resolved`.
- When reviewers give a pair different grades, scoring needs a `resolved`
  label for it. `agreement()` reports kappa and exact agreement.
- **Every report carries its set's wording:**
  - `lawyer-labelled (N query cases, reviewer(s) …)`;
  - `SYNTHETIC labels …: tests the machinery, not legal quality`;
  - `citation-derived proxy labels …: NOT lawyer relevance`.

**Annotation support:**
- `candidate_pool()`: the union of each method's top 20, plus extra keys,
  in an order fixed by a hash, so it hides which method found what;
- `pool_rows()`: blank labelling rows for the reviewer.

**Citation proxy:** `citation_proxy()` turns a query judgment's exact
citation matches into proxy labels (grade 2, reviewer `citation-proxy`).
They are signals, not lawyer relevance, and are reported as such.

**Not yet done** (it needs the approved corpus): running a graded set
against the search modes on the evaluation database, and the first report.
No labels exist, and none are generated here.

## 4. Corpus integrity (Batch 5)

The genuine corpus files are outside Git (`server/var/judgments/sci-tm-v2/`).
Its reference record is committed:
`docs/verification/batch2/corpus-sci-tm-v2.lock.json`. The record holds the
approved manifest hash, each judgment's import-copy and original hash, the
transformation flag and the official addresses. It contains no judgment
text.

**Check**, read-only (it never downloads, replaces or modifies a file). Run
from `server/`:

```
.venv\Scripts\python scripts/verify_corpus_integrity.py verify var/judgments/sci-tm-v2 --lock ../docs/verification/batch2/corpus-sci-tm-v2.lock.json [--database lexflow_e2e]
```

It exits 1 and lists every problem, including:
- a changed manifest, import copy or original;
- a broken length-prefix relation;
- an address that is not official;
- a missing PDF, or an extra one;
- with `--database`, records that do not match the manifest.

**Last run:** 2026-10-27, 17 judgments, 0 problems.

**Tests:** `server/tests/test_corpus_integrity.py` (8). They use invented
bytes in a temporary folder and need no database.

**Re-acquisition** (on a fresh machine, the folder is absent):
1. Download each of the 17 addresses in the lock by hand or with care,
   one at a time.
2. Check each download against its `original_sha256`.
3. Rebuild the import copies with `scripts/prepare_official_judgments.py`.

A new lock is written only with `write-lock` for an approved manifest, and
it never overwrites an existing one.

## 5. Real-model evaluation (Milestone 8)

**Harness:** `server/scripts/evaluate_analysis_real.py`. Tests:
`server/tests/test_real_model_harness.py` (12).

**Plan-only by default.** Every model call needs `--execute --approval
<SHA-256 of the exact plan>`, with Gemini configured.

**Two scopes, never mixed:**

| Scope | Flag | Results folder | Plan hash | Status |
|---|---|---|---|---|
| Synthetic | default | `server/var/eval/real-model/` | `f007eb87…` | Run on 2026-10-27; **15 of 21 complete** |
| Genuine | `--judgments genuine` | `server/var/eval/real-model-genuine/` | `d106434b…` | **Not approved, not run** |

- A plan stamp in each results folder (`plan-sha256.txt`) makes execution
  refuse a folder that already holds another plan's results.
- `--retry-failed` retries only transient API failures:
  - at most 3 attempts per run;
  - back-off of 30 s, then 60 s;
  - a ledger-enforced ceiling of 63 calls per plan.
- **The six incomplete synthetic runs** (S3 #2, S4 #2–3, S5 #3, S6 #1 and
  #3) are **infrastructure failures**: Google HTTP 503 or 504 on every
  attempt. They are **not model failures**; no model answer was received
  for them.

Results and limitations: `docs/verification/batch3/REAL_MODEL_APPROVAL_REQUEST.md`.
