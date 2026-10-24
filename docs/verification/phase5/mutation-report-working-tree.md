# Phase 5 mutation checks

Working tree on commit `6b8f865` with uncommitted changes (target files identified by SHA-256 below); run 2026-10-24 18:28 UTC; script `docs/verification/phase5/run_mutation_checks.py` (raw output: `mutation-output-working-tree.log`).

Each row removes or weakens one guard, runs the listed tests, and restores the file byte-for-byte (checked after every row, and `git status` of every target file checked clean at the end). **Caught** = the tests failed with the guard removed.

**Result: 61 of 61 caught.**

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
| C-3 | a missing key is reported (the setting named to administrators only) | `server/lexflow/analysis/provider.py` | `tests/test_analysis_config.py tests/test_analysis_provider.py` | 1 | caught |
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
| M9-1 | an unknown provider fails closed | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| M9-2 | a run confirmed for another provider sends nothing | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-3 | a used-up daily quota is not retried | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| M9-4 | provider messages do not name settings | `server/lexflow/analysis/provider.py` | `tests/test_analysis_provider.py` | 1 | caught |
| M9-5 | only administrators see which setting is missing | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-6 | an unexpected provider error fails the run, not the worker | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-7 | an answer that could not be checked is never stored | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-8 | an interrupted run fails after its last attempt | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-9 | sources changed since the run are reported | `server/lexflow/api/analysis.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-10 | the pipeline versions are stored with a run | `server/lexflow/analysis/runs.py` | `tests/test_analysis_runs.py` | 1 | caught |
| M9-11 | a provider-schema change needs a new schema version | `server/lexflow/analysis/output.py` | `tests/test_analysis_output.py` | 1 | caught |
| M9-12 | the "outcome" key is discarded | `server/lexflow/analysis/output.py` | `tests/test_analysis_output.py` | 1 | caught |
| M9-13 | contradiction sources must be distinct | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| M9-14 | invented case names are removed | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| M9-15 | outcome wording is removed | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| M9-16 | invented neutral citations are removed | `server/lexflow/analysis/validation.py` | `tests/test_analysis_validation.py` | 1 | caught |
| M9-17 | synthetic imports check the database actually connected | `server/lexflow/cli/judgments.py` | `tests/test_judgment_import.py` | 1 | caught |
| M9-18 | a demo import must name the database exactly | `server/lexflow/cli/judgments.py` | `tests/test_judgment_import.py` | 1 | caught |
| M9-19 | a test database is named by a whole name part | `server/lexflow/config.py` | `tests/test_judgment_import.py` | 1 | caught |
| M9-20 | the scripted double refuses URLs that connect elsewhere (?dbname=) | `server/lexflow/config.py` | `tests/test_analysis_config.py tests/test_analysis_provider.py` | 1 | caught |
| M9-21 | changed sources are shown in the result | `src/components/workspace/AnalysisTab.tsx` | `src/pages/analysis.test.tsx` | 1 | caught |

## Target files (SHA-256, unchanged before and after)

- `server/lexflow/analysis/evidence.py` `a057d2e201ab550b21afa8d75f55339e6f79b3bc799cef47513eeaadfdfd59ed`
- `server/lexflow/analysis/output.py` `bb8e0503d7223c1b3bd22eb2f36c6449a187eb913bc192f261e0f2c424f46f71`
- `server/lexflow/analysis/provider.py` `9e288a4a90eb9e90fea53b5ca604cb2166ddb0d33ef1a1493bc97733f2085d61`
- `server/lexflow/analysis/runs.py` `69936ebd1c2cab7591cb9b174d15e9bd34b08c52d7ed0e56cf419260c4abdc61`
- `server/lexflow/analysis/validation.py` `08a9e32d77ee7f41f079d48268d1b17fc444df73a7f0f95dca487dce29e99aa7`
- `server/lexflow/api/analysis.py` `88f00e9e7d0aa9d101065c0f18923c77e3aeaa2f992ced4390f547b5bdd7dce0`
- `server/lexflow/authz.py` `9dbf7ce2f65cfebb2c6f20e82105950864f59929167a6aac3c27cc5929d1ed98`
- `server/lexflow/cli/judgments.py` `672b5fbe41c7eacbf9c4a2d36cf2e68fcffb8e6aed385a054cc2fab649c53956`
- `server/lexflow/config.py` `7bb941867d895890b7a20ac25c7351a61a1a0d7d07f24a389229a82cd8d1b69c`
- `server/lexflow/worker.py` `6c7f10c9656ae38a44cf4a1ff775e2cfef7ae95fcb10900bd4c1ebeb16cfa9f6`
- `src/components/workspace/AnalysisTab.tsx` `7981ab848d05cc009bec81123e0ec68384f99c86c9516c6b6a8a292b5e3d99c6`
- `src/hooks/useCaseAnalysis.ts` `9248ad026c6aecded43b8b5ed0c6a6cb2ebb36806b36e3b2fc0f248f1ad34b0b`

## Failing tests per check

- **V-1**: `FAILED tests/test_analysis_validation.py::test_a_quote_from_another_passage_or_invented_is_removed`
- **V-2**: `FAILED tests/test_analysis_validation.py::test_a_fact_citing_an_unknown_passage_is_removed`; `FAILED tests/test_analysis_validation.py::test_facts_must_cite_a_case_passage_not_a_judgment`; `FAILED tests/test_analysis_validation.py::test_issues_keep_only_references_to_surviving_facts`; `FAILED tests/test_analysis_validation.py::test_nothing_verifiable_means_insufficient_evidence_not_a_guess`; `FAILED tests/test_analysis_validation.py::test_injected_instructions_cannot_add_evidence`
- **V-3**: `FAILED tests/test_analysis_validation.py::test_an_output_citing_an_unknown_judgment_is_rejected`; `FAILED tests/test_analysis_validation.py::test_injected_instructions_cannot_add_evidence`
- **V-4**: `FAILED tests/test_analysis_validation.py::test_a_too_short_quote_cannot_support_a_fact`
- **V-5**: `FAILED tests/test_analysis_validation.py::test_issues_keep_only_references_to_surviving_facts`
- **V-6**: `FAILED tests/test_analysis_validation.py::test_a_contradiction_needs_two_verified_sources`; `FAILED tests/test_analysis_validation.py::test_two_quotes_of_the_same_text_are_not_a_contradiction`
- **V-7**: `FAILED tests/test_analysis_validation.py::test_an_invented_citation_in_a_statement_is_removed`; `FAILED tests/test_analysis_validation.py::test_a_precedent_with_an_invented_citation_in_its_prose_is_removed`; `FAILED tests/test_analysis_validation.py::test_an_invented_neutral_citation_is_removed`
- **V-8**: `FAILED tests/test_analysis_validation.py::test_an_outcome_assessment_is_never_kept`
- **V-9**: `FAILED tests/test_analysis_validation.py::test_a_retrieved_judgment_is_described_from_the_collection_not_the_model`
- **V-10**: `FAILED tests/test_analysis_validation.py::test_a_fact_citing_an_unknown_passage_is_removed`; `FAILED tests/test_analysis_validation.py::test_nothing_verifiable_means_insufficient_evidence_not_a_guess`
- **O-1**: `FAILED tests/test_analysis_output.py::test_unusable_answers_are_rejected_as_a_whole[[1, 2]]`; `FAILED tests/test_analysis_output.py::test_unusable_answers_are_rejected_as_a_whole["facts"]`
- **O-2**: `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcome_assessment]`; `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcomeAssessment]`; `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcome]`; `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[prediction]`
- **P-1**: `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure0-provider-rate-limited-True]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure1-provider-rejected-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure2-provider-auth-failed-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure3-provider-auth-failed-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure4-provider-model-not-found-False]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure5-provider-unavailable-True]`; `FAILED tests/test_analysis_provider.py::test_failures_map_to_fixed_codes_and_messages[failure6-provider-unavailable-True]`; `FAILED tests/test_analysis_provider.py::test_google_status_and_reason_are_captured_from_structured_fields`
- **P-2**: `FAILED tests/test_analysis_provider.py::test_the_default_client_uses_the_key_and_no_sdk_retries`
- **P-3**: `FAILED tests/test_analysis_provider.py::test_a_request_carries_the_schema_instructions_and_limits`; `FAILED tests/test_analysis_provider.py::test_the_default_client_uses_the_key_and_no_sdk_retries`
- **P-4**: `FAILED tests/test_analysis_provider.py::test_blocked_and_empty_answers_fail[answer1-provider-blocked]`; `FAILED tests/test_analysis_provider.py::test_blocked_and_empty_answers_fail[answer2-provider-blocked]`
- **P-5**: `FAILED tests/test_analysis_provider.py::test_an_answer_cut_off_at_the_token_limit_is_marked`
- **C-1**: `FAILED tests/test_analysis_config.py::test_the_scripted_double_is_refused_outside_test_and_e2e_databases`; `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/lexflow_latest]`; `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/contest]`; `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/lexflow_test?dbname=lexflow]`; `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/lexflow_e2e?service=live]`
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
- **U-1**: `× Starting an analysis > says what is sent where, and needs explicit confirmation 220ms`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > says what is sent where, and needs explicit confirmation`
- **U-2**: `× Runs that fail or do not match > rejects a run that belongs to another case 5010ms`; `FAIL  src/pages/analysis.test.tsx > Runs that fail or do not match > rejects a run that belongs to another case`
- **U-3**: `× A finished analysis > links every fact to its document page and shows the verified quote 234ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > links every fact to its document page and shows the verified quote`
- **U-4**: `× A finished analysis > counts what was removed, with the reasons, and always shows the disclaimer 238ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > counts what was removed, with the reasons, and always shows the disclaimer`
- **U-5**: `× Starting an analysis > says what is sent where, and needs explicit confirmation 202ms`; `× Starting an analysis > offers a document as soon as its text becomes ready 61ms`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > says what is sent where, and needs explicit confirmation`; `FAIL  src/pages/analysis.test.tsx > Starting an analysis > offers a document as soon as its text becomes ready`
- **U-6**: `× A finished analysis > says plainly when no precedents were available 215ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > says plainly when no precedents were available`
- **M9-1**: `FAILED tests/test_analysis_provider.py::test_an_unknown_provider_fails_closed_and_never_reaches_gemini[local]`; `FAILED tests/test_analysis_provider.py::test_an_unknown_provider_fails_closed_and_never_reaches_gemini[openai]`; `FAILED tests/test_analysis_provider.py::test_an_unknown_provider_fails_closed_and_never_reaches_gemini[Gemini]`; `FAILED tests/test_analysis_provider.py::test_an_unknown_provider_fails_closed_and_never_reaches_gemini[]`; `FAILED tests/test_analysis_provider.py::test_an_unknown_provider_fails_closed_and_never_reaches_gemini[gemini ]`
- **M9-2**: `FAILED tests/test_analysis_runs.py::test_a_run_confirmed_for_another_provider_sends_nothing`
- **M9-3**: `FAILED tests/test_analysis_provider.py::test_an_exhausted_daily_quota_is_not_retried_but_a_rate_limit_is[GenerateRequestsPerDayPerProjectPerModel-FreeTier-provider-quota-exhausted-False]`; `FAILED tests/test_analysis_provider.py::test_an_exhausted_daily_quota_is_not_retried_but_a_rate_limit_is[GenerateContentDailyInputTokens-provider-quota-exhausted-False]`; `FAILED tests/test_analysis_provider.py::test_an_exhausted_daily_quota_is_not_retried_but_a_rate_limit_is[RequestsPerMonthPerProject-provider-quota-exhausted-False]`; `FAILED tests/test_analysis_provider.py::test_quota_classification_reads_only_valid_structured_fields`
- **M9-4**: `FAILED tests/test_analysis_provider.py::test_provider_messages_are_safe_for_every_staff_member[failure0]`; `FAILED tests/test_analysis_provider.py::test_provider_messages_are_safe_for_every_staff_member[failure1]`
- **M9-5**: `FAILED tests/test_analysis_runs.py::test_a_run_needs_configuration - assert (...`; `FAILED tests/test_analysis_runs.py::test_an_off_server_does_not_name_its_settings_to_advocates`
- **M9-6**: `FAILED tests/test_analysis_runs.py::test_an_unexpected_provider_error_fails_the_run_without_crashing_the_worker`
- **M9-7**: `FAILED tests/test_analysis_runs.py::test_an_error_while_checking_the_answer_never_stores_a_result`
- **M9-8**: `FAILED tests/test_analysis_runs.py::test_an_interrupted_run_is_handed_back_until_its_last_attempt[1-failed]`
- **M9-9**: `FAILED tests/test_analysis_runs.py::test_a_result_says_which_sources_changed_since_the_run`; `FAILED tests/test_analysis_runs.py::test_missing_or_unreadable_judgment_references_count_as_changed`
- **M9-10**: `FAILED tests/test_analysis_runs.py::test_the_scripted_run_ends_ready_with_verified_sources_only`
- **M9-11**: `FAILED tests/test_analysis_output.py::test_the_schema_version_names_exactly_this_schema`; `FAILED tests/test_analysis_output.py::test_the_provider_schema_has_no_array_size_keywords_but_states_the_limits`
- **M9-12**: `FAILED tests/test_analysis_output.py::test_an_outcome_assessment_is_noted_for_discarding[outcome]`; `FAILED tests/test_analysis_output.py::test_every_outcome_key_is_covered - Ass...`
- **M9-13**: `FAILED tests/test_analysis_validation.py::test_two_quotes_of_the_same_text_are_not_a_contradiction`
- **M9-14**: `FAILED tests/test_analysis_validation.py::test_an_invented_case_name_is_removed_but_known_parties_are_not`
- **M9-15**: `FAILED tests/test_analysis_validation.py::test_outcome_wording_is_removed_wherever_it_appears`
- **M9-16**: `FAILED tests/test_analysis_validation.py::test_an_invented_neutral_citation_is_removed`
- **M9-17**: `FAILED tests/test_judgment_import.py::test_the_checks_use_the_database_actually_connected_not_the_url`
- **M9-18**: `FAILED tests/test_judgment_import.py::test_a_demo_import_into_a_non_test_database_must_name_it_exactly`
- **M9-19**: `FAILED tests/test_judgment_import.py::test_synthetic_sources_are_refused_outside_test_databases`; `FAILED tests/test_judgment_import.py::test_a_test_database_is_named_by_a_whole_name_part[LEXFLOW-TEST-True]`; `FAILED tests/test_judgment_import.py::test_a_test_database_is_named_by_a_whole_name_part[lexflow_latest-False]`; `FAILED tests/test_judgment_import.py::test_a_test_database_is_named_by_a_whole_name_part[contest-False]`; `FAILED tests/test_judgment_import.py::test_a_test_database_is_named_by_a_whole_name_part[lexflowtest-False]`; `FAILED tests/test_judgment_import.py::test_a_test_database_is_named_by_a_whole_name_part[e2etest-False]`
- **M9-20**: `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/lexflow_test?dbname=lexflow]`; `FAILED tests/test_analysis_config.py::test_the_scripted_double_needs_a_real_test_database_name[postgresql+psycopg://<user>:***@127.0.0.1/lexflow_e2e?service=live]`
- **M9-21**: `× A finished analysis > says which sources changed after the run, and keeps the verified quotes 457ms`; `FAIL  src/pages/analysis.test.tsx > A finished analysis > says which sources changed after the run, and keeps the verified quotes`
