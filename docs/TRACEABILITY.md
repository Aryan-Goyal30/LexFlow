# Requirements traceability

Maps the requirements of `docs/SRS.md` to code and to the tests that check
them. Paths are relative to the repository root.

| Req | Implementation | Tests |
|---|---|---|
| FR-1 | `server/lexflow/auth/`, `api/auth.py`, `cli/users.py` | `server/tests/test_auth*.py`, `test_cli_users.py`, `e2e/auth.spec.ts` |
| FR-2 | `server/lexflow/authz.py`, `main.py` (routers) | `test_access_required.py`, `test_case_access.py`, `test_portal.py`, `e2e/roles.spec.ts` |
| FR-3 | `api/cases.py`, `services/cases.py` | `test_cases.py`, `test_case_workflows.py`, `src/pages/*.test.tsx` |
| FR-4 | `services/cases.py` (timeline) | `test_case_workflows.py` |
| FR-5 | `services/teams.py` | `test_case_access.py` |
| FR-6 | `api/hearings.py` | `test_hearings.py`, `test_hearing_schedule.py`, `src/pages/hearings*.test.tsx` |
| FR-7 | `api/clients.py` | `test_clients.py`, `src/pages/clients.test.tsx` |
| FR-8 | `api/documents.py`, `services/documents.py`, `cli/documents.py` | `test_documents.py`, `test_document_lifecycle.py`, `test_cli_documents.py`, `e2e/cases.spec.ts` |
| FR-9 | `api/portal.py` | `test_portal.py`, `e2e/portal.spec.ts` |
| FR-10 | `worker.py`, `extraction/`, `services/extraction_queue.py` | `test_worker.py`, `test_extractors.py`, `test_extraction_queue.py` |
| FR-11 | `extraction/chunking.py`, `services/document_text.py`, `src/pages/DocumentTextPage.tsx` | `test_chunking.py`, `test_document_text.py`, `e2e/document-text.spec.ts` |
| FR-12 | `embeddings.py`, `services/indexing.py`, `services/retrieval.py`, `api/search.py`, `cli/models.py` | `test_embeddings.py`, `test_indexing.py`, `test_search.py`, `docs/verification/embeddings/` |
| FR-13 | `services/judgment_import.py`, `cli/judgments.py`, migration 0010 | `test_judgment_import.py`, `test_migrations.py` |
| FR-14 | `services/judgments.py`, `api/judgments.py` | `test_judgments_api.py` |
| FR-15 | `src/components/workspace/ResearchTab.tsx`, `src/components/research/Judgments.tsx` | `src/pages/research.test.tsx`, `e2e/research.spec.ts` |
| FR-16 | `src/pages/PrecedentLibraryPage.tsx`, `src/pages/JudgmentPage.tsx` | `src/pages/research.test.tsx`, `e2e/research.spec.ts` |
| FR-17 | `lexflow/evaluation.py`, `scripts/evaluate_judgment_search.py` | `test_evaluation.py`; results in `docs/verification/phase4/judgment-eval.md` |
| NFR-1 | session gate, CSRF, `authz.py` | `test_security.py`, `test_auth.py`, mutation runners in `docs/verification/` |
| NFR-3 | `audit.py` | `test_audit_view.py`, audit assertions across API tests |
| NFR-4 | soft delete, archive; execution logs | `test_document_lifecycle.py`, `test_migrations.py` |
| NFR-5 | `config.py`, API validation | `test_extractors.py`, `test_judgments_api.py` (limits) |
| NFR-6 | AI seam, synthetic gates and badges | `useAiAssistant.test.tsx`, `test_judgment_import.py` (synthetic gates) |
| NFR-7 | OpenAPI export, type generation | `test_openapi.py`, `npm run api:check` |
| NFR-8 | all suites | `docs/verification/` |
| NFR-9 | component conventions | `e2e/research.spec.ts` (keyboard, 375 px) |
