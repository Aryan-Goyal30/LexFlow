# Annotation guide and evaluation-set plan (draft for a legal reviewer)

Status: **draft (2026-10-25). Not started.**
- No labels exist yet.
- This guide is for a qualified legal reviewer: an advocate enrolled with a
  State Bar Council, ideally practising in the chosen area.
- It produces the lawyer-labelled sets that the brief requires before Phase
  7 (register R5).

## 0. What exists today, and what it is not

| Existing set | What it is | What it is **not** |
|---|---|---|
| `synthetic-eval-v1` (`docs/verification/phase4/judgment-eval.md`): 27 queries, 13 invented judgments | a test of the search machinery; labels written by the developer | legal research quality; lawyer-labelled ground truth |
| Phase 5 analysis scenarios (`server/scripts/evaluate_analysis.py`, `docs/verification/phase5/`) | conformance to planted synthetic scenarios | the quality of real analysis |
| Sample cases and the 3 demo judgments in `lexflow` | fictional, labelled SYNTHETIC | real matters or real law |

These stay labelled SYNTHETIC. Results on them are never reported as
real-world legal quality, and they are never mixed into the lawyer-labelled
sets.

## 1. Preconditions

1. A judgment source is approved (register R4; see
   `SOURCE_CANDIDATE_SCI_JUDGMENTS.md`), and a pilot subset is imported into
   a **separate evaluation database**, never the live collection, with
   provenance.
2. The practice area or areas are chosen by the owner (Phase 4 plan, Gate 2).
3. **No real client material:**
   - query cases are built from public judgments (§3), or are synthetic case
     files;
   - real matters only after D1 (register R6).
4. The reviewer has confirmed there is no conflict with the parties in the
   query cases. They are told the labels will be stored in the repository
   under a pseudonymous reviewer id.

## 2. The three sets

| Set | Purpose (brief) | Unit labelled | Size |
|---|---|---|---|
| **E4 retrieval** | Phase 4: recall@10 and precision@10 on "10–20 sample cases with lawyer-relevance labels" | a (query case, judgment) pair | 10–20 query cases (the brief's figure) |
| **E5 analysis** | Phase 5: are the AI's facts, issues and contradictions right and complete? | a finding, or an item the lawyer lists | the same query cases, or synthetic case files |
| **E7 assessment** | Phase 7 (only after the gate): reasoning supported, uncertainty agreed | an assessment step | to be set in the Phase 7 plan |

Proposed order: E4, then E5, then E7. Run a **pilot of 2 query cases**
first, to test this guide and measure the time it takes, before committing
to the full set.

## 3. Building a query case without client data

1. The reviewer picks a decided judgment, Q, from the approved subset, in the
   chosen area.
2. From Q, the reviewer writes a **fact summary as a client file would
   present it**: parties (renamed), facts, documents, the dispute.
   - Leave out the outcome, the court's reasoning and Q's citations.
   - Keep it to 1–2 pages.
3. **Time cut-off:** only judgments decided **before** Q's decision date
   count as candidates. Q itself, and later judgments, are excluded, so the
   answer cannot leak.
4. Record:
   - `query_id`;
   - Q's source key and `cnr`, kept private from the system under test;
   - the cut-off date;
   - the area;
   - the summary text.

For E5, the same summary can be split into short synthetic "documents"
(plaint, reply, an exhibit), with deliberate contradictions where the facts
allow. Every such file is labelled SYNTHETIC (derived from a public
judgment).

## 4. E4: relevance labelling

**Candidate pool:**
- For each query case, take the union of the top 20 results from keyword,
  semantic and hybrid search on the evaluation collection, plus:
  - judgments Q itself cites that are in the collection;
  - up to 10 the reviewer adds from their own research, if in the
    collection.
- Shuffle the pool, and hide which method found each result.

**Grade each candidate** (read the judgment's relevant passage, not just the
title):

| Grade | Meaning |
|---|---|
| 3 | Directly on point: a lawyer would cite it for this dispute |
| 2 | Relevant: the same legal question or principle, usable with care |
| 1 | Marginal: background or the same statute, but not useful here |
| 0 | Not relevant |

- **Relevant** for recall@10 and precision@10 means grade 2 or 3.
- The graded scale is kept for later measures such as nDCG.
- For each grade-2 or grade-3 judgment, the reviewer writes **one line**
  saying why, and notes the paragraph or page.
- **Known limit:** recall is measured against the pool. A relevant judgment
  that no method found and the reviewer did not add is missed. Report this
  limit with every result.

## 5. E5: analysis labelling

**First, independently of the AI:** for each query case, the reviewer lists
the material **facts**, **legal issues** and **contradictions** between
documents, each with the document and page it rests on.

**Then, on a Phase 5 run:** the reviewer judges each AI finding with the
Phase 6 review controls, plus one label from:
- **supported and material**: the cited quote supports it, and it matters;
- **supported but immaterial**;
- **unsupported or wrong**;
- **duplicate**.

From these, measure:
- **precision**: the share of findings that are supported and material;
- **recall**: the share of the reviewer's listed items that the AI found.

**Constraint:** real-model runs need the owner's approval and budget
(register R7). Until then, E5 can only be prepared, not scored.

## 6. E7: assessment labelling (only after the Phase 7 gate)

Rate each reasoning step:
- **supported by the cited precedent** / **partly** / **not**.

Then rate the assessment's uncertainty category:
- **agree** / **too confident** / **too cautious**.

Rubric wording is to be agreed with the reviewer (Phase 7 proposal §5, Q2
and Q3).

## 7. Agreement and quality control (proposed)

- **Double labelling:** if a second reviewer is available, they label at
  least 3 query cases independently. Report agreement: Cohen's kappa on
  relevant versus not relevant, and raw agreement on grades.
  - Disagreements are discussed and resolved, and the resolution is noted.
  - If agreement is low, refine the guide before the full set; the metric is
    unreliable until then.
- **Re-check:** the reviewer re-labels 1 query case a week later, to check
  consistency.
- **Do not show the reviewer** which system or setting produced a candidate.

## 8. Record format (stored in the repository, as the brief asks)

`server/tests/fixtures/eval/lawyer/<set>-v<N>/`, one folder per set version:
- `queries.jsonl`: `query_id`, `area`, `cutoff_date`, `summary`,
  `source_key`, `cnr` (Q's own; never sent to the system), `guide_version`.
- `labels.jsonl`, one line per label: `query_id`, `judgment` (source key and
  `cnr`), `grade`, `reason`, `passage` (page or paragraph), `reviewer`
  (pseudonymous id), `labelled_on`, `minutes_spent`.
- `README.md`: reviewer qualification (stated, not verified by LexFlow);
  dates; the source subset with its manifest SHA-256; the guide version;
  known limits.

**Results:** results go in `docs/verification/<phase>/`, with the commit,
the model and prompt versions, the dataset hashes, and the words
"lawyer-labelled (N query cases, reviewer(s) …)". Synthetic results keep
their SYNTHETIC label.

## 9. Thresholds: how they are set (proposal only; no values here)

1. Measure the current system on the finished sets (the baseline).
2. The owner and the reviewer go through the misses together.
3. For each metric, the owner sets:
   - a minimum, with a written reason (for example "no worse than keyword
     search alone, and at least … recall@10");
   - which failures are unacceptable at any rate (for example a grade-3
     judgment never retrieved for a query case).
4. Record the values and reasons in the Phase 7 plan before implementation.

The safety gates S1–S6 in `docs/PHASE7_PROPOSAL.md` are not thresholds of
this kind: they restate the brief and are absolute.

## 10. Effort and privacy notes for the reviewer

- **Time:** measure on the pilot. A pool holds at most 3 × 20 search
  results, plus Q's citations, plus up to 10 additions. It is smaller where
  the methods overlap.
- **What is stored:** labels, short reasons and the reviewer's pseudonymous
  id. No personal data about the reviewer beyond what they agree to.
- **Public judgments still name real people.** Summaries rename the
  parties, and nothing from a query case is shown outside the evaluation.
