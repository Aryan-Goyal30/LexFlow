# Phase 5 mutation checks

Commit `e57aebc`; run 2026-10-20 11:38 UTC; script `docs/verification/phase5/run_mutation_checks.py` (raw output: `mutation-output.log`).

Each row removes or weakens one guard, runs the listed tests, and restores the file byte-for-byte (checked after every row, and `git status` of every target file checked clean at the end). **Caught** = the tests failed with the guard removed.

**Result: 40 of 40 caught.**

| ID | Guard | File | Tests run | Exit | Result |
|---|---|---|---|---|---|
| V-1 | a quote must occur in the passage it cites | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-2 | a fact citing an unknown passage is removed (not re-pointed) | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-3 | an output citing an unknown judgment is rejected | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-4 | very short quotes cannot support a fact | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-5 | issues keep only references to surviving facts | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-6 | a contradiction needs two verified sources | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-7 | invented law-report citations are removed | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-8 | a returned outcome assessment is counted as removed | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-9 | precedent titles come from the collection, not the model | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| V-10 | nothing verifiable means insufficient evidence | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| O-1 | the answer must be a JSON object | `server/lexflow/analysis/output.py` | `tests/test_analysis_output.py` | 1 | caught |
| O-2 | outcome keys are noticed | `server/lexflow/analysis/output.py` | `tests/test_analysis_output.py` | 1 | caught |
| P-1 | provider error text is never passed on | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| P-2 | the SDK makes no retries of its own | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| P-3 | the timeout is given in milliseconds | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| P-4 | blocked answers fail | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| P-5 | a cut-off answer is marked truncated | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| C-1 | the scripted double is refused outside test/e2e databases | `server/lexflow/config.py` | `tests/test_analysis_config.py tests/test_analysis_provider.py` | 1 | caught |
| C-2 | a blank key counts as missing | `server/lexflow/config.py` | `tests/test_analysis_config.py tests/test_analysis_provider.py` | 1 | caught |
| C-3 | a missing key is reported by name | `server/lexflow/analysis/provider.py` | `tests/test_analysis_config.py tests/test_analysis_provider.py` | 1 | caught |
| E-1 | evidence comes only from the case's own documents | `server/lexflow/analysis/evidence.py` | `tests/test_analysis_evidence.py` | 1 | caught |
| E-2 | deleted documents are never evidence | `server/lexflow/analysis/evidence.py` | `tests/test_analysis_evidence.py` | 1 | caught |
| R-1 | only advocates on the case and administrators start runs | `server/lexflow/authz.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-2 | the user must confirm the transmission | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-3 | only sample cases are accepted unless client data is allowed (API) | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-4 | the worker re-checks the sample-case gate before sending | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-5 | only ready documents of this case may be selected | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-6 | the hourly limit per person | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-7 | a result is stored only by the worker holding the run | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-8 | starting a run is audited | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-9 | a run is read only through its own case | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-10 | a busy provider is retried only after a pause | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-11 | no provider call when there is no text | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| R-12 | the worker skips analysis without migration 0011 | `server/lexflow/worker.py` | `tests/test_analysis_runs.py` | 1 | caught |
| U-1 | nothing is sent without explicit confirmation | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |
| U-2 | a run of another case is never shown | `src/hooks/useCaseAnalysis.ts` | `src/pages/analysis.test.tsx` | 1 | caught |
| U-3 | fact links open the cited page | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |
| U-4 | the disclaimer is shown with every result | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |
| U-5 | documents without text cannot be chosen | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |
| U-6 | no precedents available is said plainly | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |

## Failing tests per check

- **V-1**: `FAILED tests/test_analysis_validation.py::test_a_quote_from_another_passage_or_invented_is_removed`
- **V-2**: `FAILED tests/test_analysis_validation.py::test_a_fact_citing_an_unknown_passage_is_removed`; `FAILED tests/test_analysis_validation.py::test_facts_must_cite_a_case_passage_not_a_judgment`; `FAILED tests/test_analysis_validation.py::test_issues_keep_only_references_to_surviving_facts`; `FAILED tests/test_analysis_validation.py::test_nothing_verifiable_means_insufficient_evidence_not_a_guess`; `FAILED tests/test_analysis_validation.py::test_injected_instructions_cannot_add_evidence`
- **V-3**: `FAILED tests/test_analysis_validation.py::test_an_output_citing_an_unknown_judgment_is_rejected`; `FAILED tests/test_analysis_validation.py::test_injected_instructions_cannot_add_evidence`
- **V-4**: `FAILED tests/test_analysis_validation.py::test_a_too_short_quote_cannot_support_a_fact`
- **V-5**: `FAILED tests/test_analysis_validation.py::test_issues_keep_only_references_to_surviving_facts`
- **V-6**: `FAILED tests/test_analysis_validation.py::test_a_contradiction_needs_two_verified_sources`
- **V-7**: `FAILED tests/test_analysis_validation.py::test_an_invented_citation_in_a_statement_is_removed`; `FAILED tests/test_analysis_validation.py::test_a_precedent_with_an_invented_citation_in_its_prose_is_removed`
- **V-8**: `FAILED tests/test_analysis_validation.py::test_an_outcome_assessment_is_never_kept`
- **V-9**: `FAILED tests/test_analysis_validation.py::test_a_retrieved_judgment_is_described_from_the_collection_not_the_model`
- **V-10**: `FAILED tests/test_analysis_validation.py::test_a_fact_citing_an_unknown_passage_is_removed`; `FAILED tests/test_analysis_validation.py::test_nothing_verifiable_means_insufficient_evidence_not_a_guess`
- **O-1**: `FAILED tests/test_analysis_output.py::test_unusable_answers_are_rejected_as_a_whole[[1, 2]]`; `FAILED tests/test_analysis_output.py::test_unusable_answers_are_rejected_as_a_whole["facts"]`
- **O-2**: `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcome_assessment]`; `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcomeAssessment]`; `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[prediction]`
- **P-1**: `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure0-provider-rate-limited-True]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure1-provider-rejected-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure2-provider-auth-failed-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure3-provider-auth-failed-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure4-provider-model-not-found-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure5-provider-unavailable-True]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure6-provider-unavailable-True]`
- **P-2**: `FAILED tests/test_analysis_provider.py::test_the_default_client_uses_the_key_and_no_sdk_retries`
- **P-3**: `FAILED tests/test_analysis_provider.py::test_a_request_carries_the_schema_instructions_and_limits`; `FAILED tests/test_analysis_provider.py::test_the_default_client_uses_the_key_and_no_sdk_retries`
- **P-4**: `FAILED tests/test_analysis_provider.py::test_blocked_and_empty_answers_fail[answer1-provider-blocked]`; `FAILED tests/test_analysis_provider.py::test_blocked_and_empty_answers_fail[answer2-provider-blocked]`
- **P-5**: `FAILED tests/test_analysis_provider.py::test_an_answer_cut_off_at_the_token_limit_is_marked`
- **C-1**: `FAILED tests/test_analysis_config.py::test_the_scripted_double_is_refused_outside_test_and_e2e_databases`
- **C-2**: `FAILED tests/test_analysis_config.py::test_analysis_is_off_by_default - Asser...`; `FAILED tests/test_analysis_config.py::test_a_blank_key_counts_as_missing - As...`; `FAILED tests/test_analysis_provider.py::test_provider_for_reports_what_is_missing`
- **C-3**: `FAILED tests/test_analysis_provider.py::test_provider_for_reports_what_is_missing`
- **E-1**: `FAILED tests/test_analysis_evidence.py::test_passages_come_only_from_selected_live_ready_documents_of_the_case`
- **E-2**: `FAILED tests/test_analysis_evidence.py::test_passages_come_only_from_selected_live_ready_documents_of_the_case`
- **R-1**: `FAILED tests/test_analysis_runs.py::test_setup_with_a_configured_provider - a...`; `FAILED tests/test_analysis_runs.py::test_case_permissions_say_who_may_run_an_analysis`; `FAILED tests/test_analysis_runs.py::test_paralegals_may_read_but_not_start - ...`
- **R-2**: `FAILED tests/test_analysis_runs.py::test_a_run_needs_explicit_confirmation_and_valid_input`
- **R-3**: `FAILED tests/test_analysis_runs.py::test_client_cases_are_refused_unless_the_owner_allows_client_data`
- **R-4**: `FAILED tests/test_analysis_runs.py::test_the_worker_checks_the_case_again_before_sending_anything`
- **R-5**: `FAILED tests/test_analysis_runs.py::test_only_ready_live_documents_of_this_case_may_be_selected`
- **R-6**: `FAILED tests/test_analysis_runs.py::test_the_hourly_limit_per_person - assert...`
- **R-7**: `FAILED tests/test_analysis_runs.py::test_a_result_is_discarded_when_the_run_is_no_longer_held`
- **R-8**: `FAILED tests/test_analysis_runs.py::test_a_run_is_queued_audited_and_one_at_a_time`
- **R-9**: `FAILED tests/test_analysis_runs.py::test_a_run_of_another_case_is_not_found_through_this_case`
- **R-10**: `FAILED tests/test_analysis_runs.py::test_a_busy_provider_is_retried_later_then_the_run_fails`
- **R-11**: `FAILED tests/test_analysis_runs.py::test_without_text_at_run_time_no_provider_is_called`
- **R-12**: `FAILED tests/test_analysis_runs.py::test_the_worker_leaves_analysis_alone_when_it_is_unavailable`
- **U-1**: `× Starting an analysis > says what is sent where, and needs explicit confirmation 345ms`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > says what is sent where, and needs explicit confirmation`
- **U-2**: `× Runs that fail or do not match > rejects a run that belongs to another case 5009ms`; `FAIL  src/pages/analysis.test.tsx > Runs that fail or do not match > rejects a run that belongs to another case`
- **U-3**: `× A finished analysis > links every fact to its document page and shows the verified quote 301ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > links every fact to its document page and shows the verified quote`
- **U-4**: `× A finished analysis > counts what was removed, with the reasons, and always shows the disclaimer 302ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > counts what was removed, with the reasons, and always shows the disclaimer`
- **U-5**: `× Starting an analysis > says what is sent where, and needs explicit confirmation 311ms`; `× Starting an analysis > offers a document as soon as its text becomes ready 86ms`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > says what is sent where, and needs explicit confirmation`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > offers a document as soon as its text becomes ready`
- **U-6**: `× A finished analysis > says plainly when no precedents were available 381ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > says plainly when no precedents were available`
