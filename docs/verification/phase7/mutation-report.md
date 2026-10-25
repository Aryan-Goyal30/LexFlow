# Phase 7 mutation checks (outcome assessment demo)

Working tree on commit `0ce62a4`; run 2026-10-25 09:18 UTC; script `docs/verification/phase7/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests and restores the file byte for byte (checked after every row; every target's SHA-256 is unchanged at the end). **Caught** = the tests failed with the guard removed.

**Result: 25 of 25 caught.**

| ID | Guard | File | Tests | Exit | Result |
|---|---|---|---|---|---|
| P7-1 | a cited precedent must be an accepted comparison of the run | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-2 | a quote must occur in the cited judgment passage | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-3 | a reasoning step may rest only on accepted findings | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-4 | probability and percentage wording is rejected | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-5 | outcome predictions and definitive claims are rejected | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-6 | a synthetic judgment may not be called real law | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-7 | a forbidden summary withholds the whole assessment | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-8 | no assessment without a verified precedent | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-9 | the uncertainty category must fit the cited stances | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-10 | the synthetic flag comes from the collection, not the answer | `server/lexflow/assessment/validation.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-11 | fields outside the contract (scores, relabelling) are counted | `server/lexflow/assessment/output.py` | `tests/test_assessment_validation.py` | 1 | caught |
| P7-12 | rejected and unreviewed findings never reach the provider | `server/lexflow/assessment/inputs.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-13 | a changed judgment passage cannot support an assessment | `server/lexflow/assessment/inputs.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-14 | no accepted finding: no provider call | `server/lexflow/assessment/inputs.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-15 | with the flag off every route answers 404 | `server/lexflow/api/assessments.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-16 | only a ready assessment can be reviewed | `server/lexflow/api/assessments.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-17 | a stale review version is refused | `server/lexflow/assessment/service.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-18 | reviewers' notes are hidden from paralegals | `server/lexflow/api/assessments.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-19 | only an accepted assessment reaches the brief | `server/lexflow/assessment/service.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-20 | with the flag off the brief has no assessment | `server/lexflow/api/reviews.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-21 | the flag is refused outside a test or e2e database | `server/lexflow/config.py` | `tests/test_assessments_api.py` | 1 | caught |
| P7-22 | only advocates on the case and administrators generate | `server/lexflow/authz.py` | `tests/test_assessments_api.py` | 1 | caught |
| U7-1 | the card appears only when the server enables the feature | `src/components/workspace/AnalysisTab.tsx` | `src/pages/assessment.test.tsx` | 1 | caught |
| U7-2 | synthetic or scripted output carries the demonstration banner | `src/components/workspace/OutcomeAssessment.tsx` | `src/pages/assessment.test.tsx` | 1 | caught |
| U7-3 | review controls only for those who may review | `src/components/workspace/OutcomeAssessment.tsx` | `src/pages/assessment.test.tsx` | 1 | caught |

## Target files (SHA-256, unchanged before and after)

- `server/lexflow/api/assessments.py` `cf76f1b874aef79fd25407b86259fa716fe7f82a77be6c6ff29278032bcfda4a`
- `server/lexflow/api/reviews.py` `a253b968472ce33a65fd4b498d0eef5516fcab92f4b4bc87e0dfa5af0a2b42c7`
- `server/lexflow/assessment/inputs.py` `fbae33d6e7c4c15efb2af0a38a7935e2a957470c0bd282eea0c2aa710544a827`
- `server/lexflow/assessment/output.py` `a1885e509ec59ba124aadd3e017db467021bf5b5cee3ab2bc5b5b31ee265435a`
- `server/lexflow/assessment/service.py` `6a0691e0bce812c708e140345bf7828847977a264cafe7f012dad0ae8641c6c1`
- `server/lexflow/assessment/validation.py` `cfef96c91183f1a7bede33d7bdefedc9987069300215e4d4a1263833013ecbf9`
- `server/lexflow/authz.py` `602e4304211cfe768327ee6d9caf8a8cb47026b50a10a9645efb05cb6fdc8447`
- `server/lexflow/config.py` `d5751d36edeb91d5c2e6c64065d8f5de077981eba0198b8080e822d704ceaed7`
- `src/components/workspace/AnalysisTab.tsx` `ed6cffa120ecc515cf128699552985a2af005c3b20ee648f6c630f1d765461fa`
- `src/components/workspace/OutcomeAssessment.tsx` `42773d6347fee0a11da15931509a00944a700efa7264cb750dc3c79639d8c185`
