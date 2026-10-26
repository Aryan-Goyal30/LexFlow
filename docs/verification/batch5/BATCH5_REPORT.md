# Batch 5: Milestones 9 and 10 (Phase 7 validation; reproducibility and release readiness)

**Date:** 2026-10-26.

**Status:** in progress, non-destructive work only. Milestone 8's real-model
run waits for the owner's approval (plan `f007eb87…`). Nothing here claims
release readiness.

## Milestone 9: Phase 7 outcome assessment

**Defect found and fixed: the demo could use a genuine judgment.**
- **The problem:** once 17 genuine judgments were in `lexflow_e2e` (Batch 2),
  an accepted precedent comparison could point at one. The scripted
  assessment would then:
  - assign it a "stance" by position;
  - state, wrongly, that "the collection holds synthetic test judgments
    only".
- **The fix:** `assessment/inputs.py` gains a new gate,
  `genuine-precedents`. An assessment whose accepted precedents include a
  non-synthetic judgment answers **insufficient**, with the reason: the
  assessment is synthetic-only until its Phase 7 gates are met. The scripted
  wording now reads "this demonstration uses synthetic test judgments only".
- **Tests:**
  - `test_a_genuine_judgment_never_supports_the_synthetic_demo_assessment`
    (through the API);
  - `test_the_gate_names_genuine_precedents_only_when_findings_exist`
    (unit).

**Evidence matrix:**

| Item | Evidence | Status |
|---|---|---|
| Uses lawyer-reviewed findings only | `test_only_accepted_findings_reach_the_provider_never_notes_or_excluded_ones`; `inputs.gather` (accepted or edited only) | Verified |
| Traceable precedent passages | changed passages excluded (`test_a_changed_judgment_passage_cannot_support_an_assessment`); validation checks references | Verified |
| No genuine judgment in the synthetic demo | new `genuine-precedents` gate | **Fixed in Batch 5** |
| Missing evidence and limitations; facts, inferences and uncertainty kept separate | assessment schema and validation; `evaluate_assessment.py` (24 SYNTHETIC scenarios: **24 as expected, 0 not**, run 2026-10-26) | Verified on synthetic scenarios |
| No invented citations, unsupported predictions or numeric probabilities | assessment validation (`unverified-citation`, `unexpected-field`, …); `test_a_misleading_summary_withholds_the_whole_assessment`; Phase 7 mutation checks | Verified (see Verification) |
| Decision support, not a legal determination | `label="decision-support"`, `demo_only`; UI labels (Phase 7 M2) | Verified |
| Invalid output rejected or withheld | provider-failure and misleading-summary tests | Verified |
| Review history and acceptance workflow kept | `test_review_keeps_the_original_and_follows_the_phase6_rules`; the review race test | Verified |
| Real model never used | `test_a_real_model_is_never_used_for_assessments`; the settings guard | Verified |
| Predictive validity | — | **Not established.** No expert-labelled dataset exists, so the feature stays an explicitly limited research prototype, off by default and synthetic-only |

**Gates still unmet** for any real use (register R4, R5, R5a, R6):
- an approved judgment source for this purpose;
- lawyer-labelled evaluation sets;
- thresholds set after a baseline;
- the privacy sign-off (D1) for real cases;
- an approved real-model evaluation.

## Milestone 10: reproducibility and release readiness

**Plan:** document and verify, in order of value, without risky changes.

| Item | Where | Status |
|---|---|---|
| Setup and configuration (variable names only) | `README.md` Getting started; `server/README.md` First-time setup and settings | Exists; not re-run from a clean machine in this batch |
| Safe demo preparation and clean-up | `docs/DEMO_GUIDE.md` §4: `accounts` instead of `prepare` for the persistent corpus database; never `down -v` | **Updated** in Batches 2 and 5 |
| Demo and production configuration kept apart | settings guards (scripted provider, demo mode, assessment only on test or e2e databases); a secure cookie required in production | Documented and tested |
| Database identity verification | the marker and `current_database()` checks (`lexflow/demo.py`, `e2e.py`, the batch scripts) | Documented and tested |
| Dataset provenance and licence | `docs/verification/batch2/` (source report, corpus inventory, final import review) | Exists |
| Corpus integrity and reproducibility | **`scripts/verify_corpus_integrity.py`** (read-only) checks the corpus against the committed lock `docs/verification/batch2/corpus-sci-tm-v2.lock.json`: the approved manifest hash, every import copy and original as served, the length-prefix relation, the official hosts, no missing or extra PDF, and optionally the database records. On 2026-10-27: 17 judgments, **0 problems** (`tests/test_corpus_integrity.py`, 8 tests). Re-acquisition is manual: the lock lists all 17 official addresses with the original hashes a fresh download must match. Nothing is fetched automatically | **Done** (integrity); re-fetch manual |
| Migrations and safeguards | `server/README.md` Migrations; live `lexflow` stays at 0012 (0013 and 0014 not applied; applying them needs approval) | Documented |
| Test and evaluation commands, with real results | `README.md` Testing; `DEMO_GUIDE.md` §7; the batch reports | Exists |
| Known limitations and real-world gates | `README.md` Limitations; batch reports | Partly updated (README status, Batch 5) |
| Synthetic demo results versus genuine research | `DEMO_GUIDE.md` §6 (**updated**); badges and filters in the UI | Updated |
| External services and approvals | Gemini (owner approval; billing tier); judgment acquisition (approved) | Documented in the batch reports |
| Development brief | `docs/DEVELOPMENT_BRIEF.md` is protected (hash unchanged); no change proposed | — |

### Release-readiness checklist (2026-10-27)

| Area | State | Blocking release? |
|---|---|---|
| Automated tests and static checks | Pass (see Verification) | No |
| Database isolation and destructive-script guards | Identity and marker checks, a refusal to drop genuine data, Playwright isolated | No |
| Genuine corpus: provenance, integrity, attribution | 17 judgments imported to `lexflow_e2e` with provenance; integrity verified against the lock | No (demo and evaluation use) |
| Licence and legal basis for wider use | Copyright policy verified; unresolved questions recorded (storage and indexing, the two headnotes, s. 52, collection method) | **Yes:** a lawyer's opinion is needed before production use |
| Real AI analysis | Prompt-injection and grounding safeguards (`grounding-5`). The synthetic-only real-model run (2026-10-27): **15 of 21 complete**, and 6 incomplete on Google HTTP 503/504, which are infrastructure failures, not model failures. In the completed runs: planted contradictions 11 of 11, injection never followed (5 of 5), 0 items removed. The genuine-judgment run is separate (its own plan hash and results folder) and **not approved** | **Yes:** run the approved evaluation, then a lawyer reviews legal quality |
| Retrieval quality | First evaluation with model-generated and proxy labels only | **Yes:** lawyer-labelled E4 sets are needed |
| Outcome assessment | Off by default; synthetic-only; `genuine-precedents` gate; 25 of 25 mutations caught | **Yes:** for any real use, see the Milestone 9 gates |
| Privacy (D1) | Analysis limited to sample cases; no client data sent | **Yes:** privacy sign-off for real cases |
| Security | Focused review; residual risks listed (Batch 4) | **Partly:** a less-privileged database role and a deployment review |
| Page references | PDF pages; printed-page offset documented | No (documented limitation) |
| Live database | At 0012; 0013 and 0014 not applied | **Yes:** the migration needs approval, a backup and a rehearsal |
| Version control | Batches 1–5 uncommitted on `10a44c5` | **Yes:** commit after review |

**Conclusion:** not release-ready. Next, in this order:
1. commit after the owner's review;
2. the real-model evaluation:
   - first the synthetic-only plan `f007eb87…`, once approved and the
     billing tier confirmed;
   - then, for real legal analysis, the genuine-judgment plan;
3. lawyer labels for retrieval and analysis;
4. the privacy sign-off;
5. the live migration.

## Verification

| Command | Result |
|---|---|
| `pytest -q` | **1232 passed**, exit 0 (`logs/pytest.txt`) |
| ruff, format, mypy, OpenAPI check | exit 0 (`logs/static-checks.txt`) |
| Phase 7 mutation checks (`docs/verification/phase7/run_mutation_checks.py`) | **25 of 25 caught**; all files restored (`logs/phase7-mutation-checks.txt`) |
| Phase 5 mutation checks (`docs/verification/phase5/run_mutation_checks.py --working-tree --label batch5`), pre-commit | First attempt stopped at C-1 (exit 3; its search text occurred three times in `config.py`) after 17 of 65, all caught (`logs/phase5-mutation-checks.txt`). After C-1's search text was made unique (the preceding line added), **65 of 65 caught**, exit 0; all 358 source files hash-identical before and after (`logs/phase5-mutation-checks-2.txt`; report `docs/verification/phase5/mutation-report-working-tree-batch5.md`) |
| `scripts/evaluate_assessment.py` | 24 SYNTHETIC scenarios, 24 as expected |
| `npm run check`, Playwright | not rerun: no front-end or app-route change in Batch 5 (the Batch 3 results stand) |
| Corpus | all 17 records match the manifest |

**Live `lexflow`:** 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
**Unchanged.** No model call was made. No commit, no push.
