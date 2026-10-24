# Phase 6 mutation checks

Working tree on commit `eada4ef`; run 2026-10-24 23:17 UTC; script `docs/verification/phase6/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests and restores the file byte for byte (checked after every row; every target's SHA-256 is unchanged at the end). **Caught** = the tests failed with the guard removed.

**Result: 19 of 19 caught.**

| ID | Guard | File | Tests | Exit | Result |
|---|---|---|---|---|---|
| P6-1 | a stale version is refused | `server/lexflow/services/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-2 | a change that alters nothing adds no history entry | `server/lexflow/services/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-3 | an edit must change the AI's wording | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-4 | a not-ready run cannot be reviewed | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-5 | a run of another case is not found through this case | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-6 | a finding must exist in the run | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-7 | paralegals may not decide on findings | `server/lexflow/authz.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-8 | notes are shown to reviewers only | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-9 | the audit event holds no note | `server/lexflow/api/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-10 | the timeline entry holds no note | `server/lexflow/services/reviews.py` | `tests/test_analysis_reviews.py` | 1 | caught |
| P6-11 | the brief holds only accepted findings | `server/lexflow/services/brief.py` | `tests/test_case_brief.py` | 1 | caught |
| P6-12 | an edited finding appears in the lawyer's wording | `server/lexflow/services/brief.py` | `tests/test_case_brief.py` | 1 | caught |
| P6-13 | synthetic judgments are labelled in the brief | `server/lexflow/services/brief.py` | `tests/test_case_brief.py` | 1 | caught |
| P6-14 | changed sources are flagged in the brief | `server/lexflow/services/brief.py` | `tests/test_case_brief.py` | 1 | caught |
| P6-15 | no brief without an accepted finding | `server/lexflow/api/reviews.py` | `tests/test_case_brief.py` | 1 | caught |
| U6-1 | review controls only for those the server allows | `src/components/workspace/AnalysisTab.tsx` | `src/pages/review.test.tsx` | 1 | caught |
| U6-2 | unreviewed findings are visibly marked | `src/components/workspace/FindingReview.tsx` | `src/pages/review.test.tsx` | 1 | caught |
| U6-3 | the export needs an accepted finding | `src/components/workspace/FindingReview.tsx` | `src/pages/review.test.tsx` | 1 | caught |
| U6-4 | review decisions are not counted as analysis input | `src/components/workspace/AnalysisTab.tsx` | `src/pages/review.test.tsx` | 1 | caught |

## Target files (SHA-256, unchanged before and after)

- `server/lexflow/api/reviews.py` `e4555e8f21f59af646488a3bea450f0c9899bc6fdae8b32318a5e7dad27c6e48`
- `server/lexflow/authz.py` `28a2022a70c4bdd4c08699fc429cc5e527c0a3844e4148307ba6caa6a70894da`
- `server/lexflow/services/brief.py` `4f2244fe27827cfcf9eda553fa1145887e28685e8fca5c09edde936249a3e109`
- `server/lexflow/services/reviews.py` `7650d5088e52fe249f1ab1e93571364316a80fe7ea1d4a07b2cb9ac4da5a9eda`
- `src/components/workspace/AnalysisTab.tsx` `02352b02ca6d99ec2ac4e04064b4559f082f2def98a74e66770487d2baa89656`
- `src/components/workspace/FindingReview.tsx` `f6763173e172cc31f7a51d873698811d9f859efed14ddea7d124350fb39c1a72`
