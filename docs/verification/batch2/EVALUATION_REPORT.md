# Batch 2: first retrieval evaluation on genuine judgments

**Date:** 2026-10-25.

**Corpus:** `sci-tm-v2`. These are 17 Supreme Court judgments imported into
`lexflow_e2e` (manifest SHA-256 `4b3134b7…cb3f3`), searched with the filter
`origin=genuine`.

**What this is:** a **technical check of the search machinery**. It is not
a measurement of legal research quality, because **no lawyer labels exist**.
Every number below carries its set's own wording, and none may be quoted
without it.

## 1. Set-up

- **Search:** the same service functions as the API, in a READ ONLY
  transaction: keyword (PostgreSQL full text), semantic (local
  `BAAI/bge-small-en-v1.5`, pinned files, nothing downloaded) and hybrid
  (reciprocal-rank fusion, k = 60).
- **Embeddings:** 30 judgments (17 genuine, 13 synthetic) and 1,280 chunks
  were embedded locally in `lexflow_e2e` with
  `scripts/index_judgments_isolated.py` (`logs/index-run.txt`).
- **Runner:** `server/scripts/evaluate_genuine_retrieval.py`.
- **Generated reports:** `evaluation/genuine-retrieval*.{json,md}`.
- **Metrics:** Recall@k, Precision@k, MRR and nDCG@k (`lexflow/evaluation.py`).
  Unlabelled results count as not relevant, and how many there were is
  reported as "unjudged".

**Two label sets, never merged:**

| Set | Labels | Size | How built |
|---|---|---|---|
| `sci-tm-known-item` v1 (`server/tests/fixtures/eval/model-generated/`) | **MODEL-GENERATED** (by Claude Code); not expert relevance | 17 queries, 20 labels | Each query paraphrases the central issue of one judgment, as found in its own text (the label's `passage`), without party or mark names. 3 grade-2 labels mark a second judgment discussing the same issue |
| `sci-tm-citation-context` v1 (built at run time; `server/var/judgments/eval/`, outside Git because it holds excerpts) | **Citation-derived proxy**; NOT lawyer relevance | 7 queries | The text around a citation of one corpus judgment in another (at most 300 characters, with the cited names and citations removed). The citing judgment is left out of its own ranking. The corpus has only 4 such citing pairs |

## 2. Results, and the change they led to

### Run A, the baseline

Keyword search required every word of the query (`websearch_to_tsquery`).

- **Keyword mode found nothing** for 14 of the 17 known-item queries, and for
  all 7 citation contexts.
- So **hybrid was identical to semantic**: its keyword half contributed
  nothing.

### Run B, the fallback tried in both modes

If no passage contains every word, keyword search ranks passages containing
any of them.

- **Keyword mode improved:**
  - known-item MRR rose from 0.176 to 0.485;
  - known-item recall@10 rose from 0.176 to 0.882.
- **Hybrid got worse:**
  - known-item MRR fell from 0.971 to 0.683;
  - citation-proxy MRR fell from 0.505 to 0.474.

  Fusion mixed weak any-word rankings into strong semantic ones.

### Run C, adopted

The fallback is used **in keyword mode only**, and hybrid keeps
every-word matches.
- Keyword keeps the gain.
- Hybrid returns to its Run A results.
- The API reports which match was used (`keywordMatch`: `all`, `any`, or
  null for semantic), and the Precedent Library says so when it falls back
  ("No passage contains every word of your search…").

### sci-tm-known-item

**MODEL-GENERATED labels (17 queries, by claude-code): a technical check, not expert relevance**

| Run | Mode | MRR@10 | Recall@1 | Recall@5 | Recall@10 | nDCG@10 | Precision@1 | Queries with no results |
|---|---|---|---|---|---|---|---|---|
| A. strict keyword (baseline) | keyword | 0.176 | 0.176 | 0.176 | 0.176 | 0.176 | 0.176 | 14 |
| A. strict keyword (baseline) | semantic | 0.971 | 0.882 | 1.000 | 1.000 | 0.964 | 0.941 | 0 |
| A. strict keyword (baseline) | hybrid | 0.971 | 0.882 | 1.000 | 1.000 | 0.964 | 0.941 | 0 |
| B. fallback in keyword and hybrid | keyword | 0.485 | 0.294 | 0.618 | 0.882 | 0.574 | 0.353 | 0 |
| B. fallback in keyword and hybrid | semantic | 0.971 | 0.882 | 1.000 | 1.000 | 0.964 | 0.941 | 0 |
| B. fallback in keyword and hybrid | hybrid | 0.683 | 0.412 | 0.941 | 1.000 | 0.748 | 0.471 | 0 |
| C. fallback in keyword only (adopted) | keyword | 0.485 | 0.294 | 0.618 | 0.882 | 0.574 | 0.353 | 0 |
| C. fallback in keyword only (adopted) | semantic | 0.971 | 0.882 | 1.000 | 1.000 | 0.964 | 0.941 | 0 |
| C. fallback in keyword only (adopted) | hybrid | 0.971 | 0.882 | 1.000 | 1.000 | 0.964 | 0.941 | 0 |

### sci-tm-citation-context

**citation-derived proxy labels (7 queries): NOT lawyer relevance**

| Run | Mode | MRR@10 | Recall@1 | Recall@5 | Recall@10 | nDCG@10 | Precision@1 | Queries with no results |
|---|---|---|---|---|---|---|---|---|
| A. strict keyword (baseline) | keyword | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 7 |
| A. strict keyword (baseline) | semantic | 0.505 | 0.286 | 1.000 | 1.000 | 0.626 | 0.286 | 0 |
| A. strict keyword (baseline) | hybrid | 0.505 | 0.286 | 1.000 | 1.000 | 0.626 | 0.286 | 0 |
| B. fallback in keyword and hybrid | keyword | 0.191 | 0.000 | 0.429 | 0.429 | 0.252 | 0.000 | 2 |
| B. fallback in keyword and hybrid | semantic | 0.505 | 0.286 | 1.000 | 1.000 | 0.626 | 0.286 | 0 |
| B. fallback in keyword and hybrid | hybrid | 0.474 | 0.286 | 0.857 | 1.000 | 0.599 | 0.286 | 0 |
| C. fallback in keyword only (adopted) | keyword | 0.191 | 0.000 | 0.429 | 0.429 | 0.252 | 0.000 | 2 |
| C. fallback in keyword only (adopted) | semantic | 0.505 | 0.286 | 1.000 | 1.000 | 0.626 | 0.286 | 0 |
| C. fallback in keyword only (adopted) | hybrid | 0.505 | 0.286 | 1.000 | 1.000 | 0.626 | 0.286 | 0 |

Run C, each query's rank of the first relevant judgment (top 10; '-' = not found):

- sci-tm-known-item:
  - keyword: ki-01=1, ki-02=7, ki-03=4, ki-04=3, ki-05=3, ki-06=1, ki-07=1, ki-08=1, ki-09=2, ki-10=6, ki-11=1, ki-12=1, ki-13=4, ki-14=-, ki-15=-, ki-16=8, ki-17=7
  - semantic: ki-01=1, ki-02=1, ki-03=1, ki-04=2, ki-05=1, ki-06=1, ki-07=1, ki-08=1, ki-09=1, ki-10=1, ki-11=1, ki-12=1, ki-13=1, ki-14=1, ki-15=1, ki-16=1, ki-17=1
  - hybrid: ki-01=1, ki-02=1, ki-03=1, ki-04=2, ki-05=1, ki-06=1, ki-07=1, ki-08=1, ki-09=1, ki-10=1, ki-11=1, ki-12=1, ki-13=1, ki-14=1, ki-15=1, ki-16=1, ki-17=1
- sci-tm-citation-context:
  - keyword: cite-nc-2025-INSC-9-sha256-843dab1-1=2, cite-nc-2025-INSC-9-sha256-ab93f02-1=-, cite-nc-2025-INSC-9-sha256-ab93f02-2=-, cite-nc-2025-INSC-9-sha256-ab93f02-3=-, cite-sha256-21ce7ca-sha256-dbcbb6d-1=2, cite-sha256-dbcbb6d-sha256-6247440-1=-, cite-sha256-dbcbb6d-sha256-6247440-2=3
  - semantic: cite-nc-2025-INSC-9-sha256-843dab1-1=1, cite-nc-2025-INSC-9-sha256-ab93f02-1=4, cite-nc-2025-INSC-9-sha256-ab93f02-2=5, cite-nc-2025-INSC-9-sha256-ab93f02-3=3, cite-sha256-21ce7ca-sha256-dbcbb6d-1=4, cite-sha256-dbcbb6d-sha256-6247440-1=2, cite-sha256-dbcbb6d-sha256-6247440-2=1
  - hybrid: cite-nc-2025-INSC-9-sha256-843dab1-1=1, cite-nc-2025-INSC-9-sha256-ab93f02-1=4, cite-nc-2025-INSC-9-sha256-ab93f02-2=5, cite-nc-2025-INSC-9-sha256-ab93f02-3=3, cite-sha256-21ce7ca-sha256-dbcbb6d-1=4, cite-sha256-dbcbb6d-sha256-6247440-1=2, cite-sha256-dbcbb6d-sha256-6247440-2=1

Run times: A. 2026-10-25T18:21:27+00:00; B. 2026-10-25T18:26:09+00:00; C. 2026-10-25T18:27:04+00:00

## 3. What the numbers support, and what they do not

**Supported, as a technical check:**
- On this 17-judgment corpus, **semantic and hybrid search find the judgment
  whose issue a query describes**: rank 1 for 16 of 17 known-item queries,
  and every target within the top 5.
- **Strict keyword search is unsuited to descriptive queries.** The any-word
  fallback makes keyword mode usable for them, but it is still far behind
  semantic search.
- For a passage quoting a cited case, semantic search places the cited
  judgment in the top 5 every time, but at rank 1 only 2 times out of 7.

**Not supported:**
- **Any statement about legal research quality.** The labels are
  model-generated or citation-derived, not a lawyer's.
- **Any comparison with other systems,** or any generalisation beyond 17
  judgments.

**Specific limitations:**
1. **Model-generated known-item queries are optimistic.** The author saw the
   judgments, and each query paraphrases one judgment's own subject, which
   favours semantic matching. Lawyer queries about a client's facts (the
   intended use) are harder.
2. **Tiny sets.** One query changes MRR by up to 0.06 (known-item) or 0.14
   (citation proxy). The citation proxy has only 7 queries, from 4 citing
   pairs; 4 of the 7 queries come from one judgment (*Pernod Ricard*).
3. **Grades.** Unlabelled judgments count as not relevant, so precision and
   nDCG are lower bounds where other judgments are in fact relevant (there
   were 150 unjudged results in the known-item top 10s).
4. **Hybrid adds nothing** over semantic here, because strict keyword
   matches are rare for descriptive queries. Hybrid's value for short,
   exact queries (names, sections, citations) was not measured.
5. **Editorial headnotes** in two legacy files (*Amritdhara*, *Parle*) are
   searchable with the judgment text. A hit on pages 1–2 of those files may
   be editorial wording.
6. **No baseline from a lawyer,** and no thresholds. Thresholds come after a
   lawyer-labelled baseline (register R5a).

## 4. Next steps that would make this a quality measurement

- **A lawyer labels E4 queries** (`docs/phase7-prerequisites/ANNOTATION_GUIDE.md`).
  `relevance_sets.candidate_pool()` gives the pooled, shuffled candidates.
  The sets load with `label_origin: lawyer`, and reports then read
  "lawyer-labelled (N query cases, reviewer(s) …)".
- **A larger corpus** (the 20–40 target) and more intra-corpus citations
  for the proxy.
- **Measure short, exact queries** (party names, sections, neutral
  citations) to judge hybrid and keyword fairly.
