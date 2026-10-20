/**
 * Generated from server/openapi.json by scripts/api-types.mjs. Do not edit.
 * Regenerate with: npm run api:types
 */

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Report whether the API is up and can reach PostgreSQL.
         */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Sign in with e-mail and password. Sets the session cookie.
         *
         *     Every refusal is the same 401 ``invalid-credentials``, whatever the reason.
         */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description End the current session (if any) and clear the cookie. Always 204.
         */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description Who is signed in. 401 ``not-authenticated`` without a live session.
         */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Change Password
         * @description Replace your own password (also a temporary one). Ends your other sessions.
         */
        post: operations["change_password_api_auth_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Clients
         * @description Clients with their contact details, by name.
         *
         *     Administrators see every client; Advocates and Paralegals only the clients
         *     of cases they may see.
         */
        get: operations["list_clients_api_clients_get"];
        put?: never;
        /**
         * Create Client
         * @description Add a client (Administrators and Advocates).
         */
        post: operations["create_client_api_clients_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients/options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Client Options
         * @description Every client, by name, without contact details: the new-case form's choices.
         *
         *     For those who may open cases (Administrators and Advocates).
         */
        get: operations["client_options_api_clients_options_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/staff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Staff
         * @description Active Advocates and Paralegals, by name: who can join a case team.
         */
        get: operations["list_staff_api_staff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/advocates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Advocates
         * @description Active users who can lead a case (role Advocate), by name.
         */
        get: operations["list_advocates_api_advocates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients/{client_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Client
         * @description A client's details and the cases of theirs you may see.
         *
         *     404 for a client none of whose cases you may see (Administrators see all).
         */
        get: operations["get_client_api_clients__client_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Client
         * @description Change a client's details (an Administrator, or an Advocate on one of their cases).
         */
        patch: operations["update_client_api_clients__client_id__patch"];
        trace?: never;
    };
    "/api/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Cases
         * @description The cases you may see (all, for an Administrator), newest first.
         */
        get: operations["list_cases_api_cases_get"];
        put?: never;
        /**
         * Create Case
         * @description Open a new case. The server assigns the case number and opening date.
         *
         *     Administrators and Advocates only; an Advocate must be the lead (403
         *     ``field-not-permitted`` otherwise).
         */
        post: operations["create_case_api_cases_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Case
         * @description One case with its documents, hearings, timeline and your permissions on it.
         *
         *     A case you may not see answers 404, exactly like one that does not exist.
         */
        get: operations["get_case_api_cases__case_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Case
         * @description Change some of a case's details. Any change adds a timeline entry by you.
         *
         *     Each field needs its own permission (``permissions.editableFields`` in the
         *     case detail); one refused field (403 ``field-not-permitted``) refuses the
         *     whole request, so nothing changes. Changing the lead advocate or the client
         *     is for Administrators only.
         */
        patch: operations["update_case_api_cases__case_id__patch"];
        trace?: never;
    };
    "/api/cases/{case_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Archive Case
         * @description Archive a case (Administrators): kept in full, read-only, hidden from lists.
         */
        post: operations["archive_case_api_cases__case_id__archive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/unarchive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Unarchive Case
         * @description Restore an archived case (Administrators).
         */
        post: operations["unarchive_case_api_cases__case_id__unarchive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/team": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Team Member
         * @description Add an Advocate (as associate) or a Paralegal to the case team.
         *
         *     The Administrator or the case's lead advocate only.
         */
        post: operations["add_team_member_api_cases__case_id__team_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/team/{member_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Remove Team Member
         * @description Take someone off the case team (the Administrator or the lead advocate).
         */
        delete: operations["remove_team_member_api_cases__case_id__team__member_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/hearings/upcoming": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Upcoming Hearings
         * @description Hearings on or after today on the cases you may see, soonest first.
         */
        get: operations["upcoming_hearings_api_hearings_upcoming_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Documents
         * @description The documents on a case, newest first.
         */
        get: operations["list_documents_api_cases__case_id__documents_get"];
        put?: never;
        /**
         * Upload Document
         * @description Attach one file to a case.
         *
         *     The file's real content must match its extension. Errors carry a ``code``:
         *     ``unsupported-type``, ``content-mismatch``, ``empty``, ``duplicate``,
         *     ``too-large`` or ``invalid-name``.
         */
        post: operations["upload_document_api_cases__case_id__documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Document Text
         * @description One page (or part) of a document's extracted text (staff on the case).
         *
         *     409 ``text-not-available`` (with the reason) until the text is ready;
         *     404 for deleted documents, documents on cases you may not see, and pages
         *     that do not exist. Each read is recorded in the audit log.
         */
        get: operations["read_document_text_api_documents__document_id__text_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/reprocess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reprocess Document
         * @description Extract a document's text again: after a failure, or to refresh it.
         *
         *     For staff who may add documents to the case; not on archived cases.
         *     409 while it is already waiting or being processed, or for file types that
         *     are not extracted.
         */
        post: operations["reprocess_document_api_documents__document_id__reprocess_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Document
         * @description Download a stored file. Sample records have no file and return 404 ``no-file``.
         */
        get: operations["download_document_api_documents__document_id__download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Document
         * @description Delete a document (Administrator or the lead advocate).
         *
         *     The document leaves the case but is kept, with its file, until restored or
         *     purged by an operator (``python -m lexflow.cli.documents purge``).
         */
        delete: operations["delete_document_api_documents__document_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/share": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Share Document
         * @description Share a document with the case's client: it appears in their portal.
         *
         *     Advocates on the case (and Administrators). Sample records cannot be
         *     shared (422 ``no-file``). Sharing it again changes nothing.
         */
        post: operations["share_document_api_documents__document_id__share_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/unshare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Unshare Document
         * @description Stop sharing a document with the client (it leaves their portal at once).
         */
        post: operations["unshare_document_api_documents__document_id__unshare_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/documents/deleted": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Deleted Documents
         * @description A case's deleted documents, most recently deleted first (Administrator or lead).
         */
        get: operations["list_deleted_documents_api_cases__case_id__documents_deleted_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore Document
         * @description Put a deleted document back on its case (Administrator or the lead advocate).
         *
         *     409 ``duplicate`` while another document on the case has the same name.
         *     Restoring a document that is not deleted changes nothing.
         */
        post: operations["restore_document_api_documents__document_id__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Case
         * @description Passages of this case's documents that match the query, best first.
         *
         *     For staff who may view the case. Results come only from the case's own
         *     documents (not deleted, text extracted) and show where each passage is.
         *     They are ranked text, not legal advice or a prediction.
         */
        get: operations["search_case_api_cases__case_id__search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/analysis/setup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Analysis Setup
         * @description What an analysis of this case would use, and whether it can start now.
         */
        get: operations["analysis_setup_api_cases__case_id__analysis_setup_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/analysis-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Analyses
         * @description The case's analysis runs, newest first (at most 50), without results.
         */
        get: operations["list_analyses_api_cases__case_id__analysis_runs_get"];
        put?: never;
        /**
         * Start Analysis
         * @description Queue an analysis of the selected documents. The worker sends their text
         *     (and any matching judgment passages) to the configured provider.
         */
        post: operations["start_analysis_api_cases__case_id__analysis_runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/analysis-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Analysis
         * @description One run of this case, with its validated result when it is ready.
         */
        get: operations["get_analysis_api_cases__case_id__analysis_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/judgments/facets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Judgment Facets
         * @description Totals, courts and years in the collection, and which search modes work.
         */
        get: operations["judgment_facets_api_judgments_facets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/judgments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Judgments
         * @description The collection, newest decision first (undated last), with stable paging.
         */
        get: operations["list_judgments_api_judgments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/judgments/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Judgments
         * @description Judgments ranked by their best passage for the query (at most 100), paged.
         *
         *     409 ``semantic-search-unavailable`` (with the reason) for semantic or
         *     hybrid search when embeddings cannot run; keyword search always works.
         */
        get: operations["search_judgments_api_judgments_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/judgments/{judgment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Judgment
         * @description One judgment with its source and the terms-of-use record of that source.
         */
        get: operations["get_judgment_api_judgments__judgment_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/judgments/{judgment_id}/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Judgment Text
         * @description One page (or part) of a judgment's text, exactly as extracted.
         */
        get: operations["judgment_text_api_judgments__judgment_id__text_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/hearings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Hearing Schedule
         * @description Hearings across the cases you may see, in a date range, soonest first.
         *
         *     Archived cases are left out; cancelled hearings only when asked for. The
         *     range may span at most a year.
         */
        get: operations["hearing_schedule_api_hearings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/hearings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Schedule Hearing
         * @description Schedule a hearing on a case. The date cannot be in the past.
         */
        post: operations["schedule_hearing_api_cases__case_id__hearings_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/hearings/{hearing_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Hearing
         * @description Change a scheduled hearing. 409 ``hearing-cancelled`` once it is cancelled.
         */
        patch: operations["update_hearing_api_hearings__hearing_id__patch"];
        trace?: never;
    };
    "/api/hearings/{hearing_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Hearing
         * @description Cancel a hearing. It stays on the case, with the reason if one is given.
         */
        post: operations["cancel_hearing_api_hearings__hearing_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Audit Log
         * @description The audit log, newest first, filtered and a page at a time (read-only).
         *
         *     Append-only in the database, but not tamper-proof against someone with
         *     database administrator rights.
         */
        get: operations["read_audit_log_api_admin_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Users
         * @description Every account, by role and name.
         */
        get: operations["list_users_api_admin_users_get"];
        put?: never;
        /**
         * Create User
         * @description Create an account with a temporary password (replaced at first sign-in).
         *
         *     The password is never returned. Client accounts need ``clientId``.
         */
        post: operations["create_user_api_admin_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update User
         * @description Change an account's name or e-mail address.
         */
        patch: operations["update_user_api_admin_users__user_id__patch"];
        trace?: never;
    };
    "/api/admin/users/{user_id}/disable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Disable User
         * @description Stop an account from signing in and end its sessions.
         *
         *     409 for your own account or the last active Administrator.
         */
        post: operations["disable_user_api_admin_users__user_id__disable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/enable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Enable User
         * @description Allow a disabled account to sign in again.
         */
        post: operations["enable_user_api_admin_users__user_id__enable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/unlock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Unlock User
         * @description Clear a lockout after repeated failed sign-ins.
         */
        post: operations["unlock_user_api_admin_users__user_id__unlock_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reset Password
         * @description Give an account a temporary password: their sessions end, and they must
         *     choose a new password at the next sign-in. Not for your own account (409).
         */
        post: operations["reset_password_api_admin_users__user_id__password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/portal/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Cases
         * @description Your cases (archived ones are not shown), newest first.
         */
        get: operations["list_cases_api_portal_cases_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/portal/cases/{case_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Case
         * @description One of your cases, with its coming hearings and the documents shared with you.
         */
        get: operations["get_case_api_portal_cases__case_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/portal/documents/{document_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Document
         * @description Download a document shared with you. Anything else answers 404.
         */
        get: operations["download_document_api_portal_documents__document_id__download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActorOut */
        ActorOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * AdminUserCreate
         * @description A new account with a temporary password the person must replace at first sign-in.
         */
        AdminUserCreate: {
            /** Name */
            name: string;
            /** Email */
            email: string;
            /**
             * Role
             * @enum {string}
             */
            role: "Administrator" | "Advocate" | "Paralegal" | "Client";
            /**
             * Clientid
             * @description Required for Client accounts.
             */
            clientId?: string | null;
            /** Temporarypassword */
            temporaryPassword: string;
        };
        /**
         * AdminUserOut
         * @description An account as administrators see it. Never includes password or session details.
         */
        AdminUserOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "Administrator" | "Advocate" | "Paralegal" | "Client";
            /** Clientid */
            clientId: string | null;
            /**
             * Clientname
             * @description For Client accounts: the client represented.
             */
            clientName: string | null;
            /** Isactive */
            isActive: boolean;
            /**
             * Islocked
             * @description Locked after repeated failed sign-ins.
             */
            isLocked: boolean;
            /**
             * Cansignin
             * @description False until a password has been set.
             */
            canSignIn: boolean;
            /** Mustchangepassword */
            mustChangePassword: boolean;
            /** Lastloginat */
            lastLoginAt: string | null;
            /** Issample */
            isSample: boolean;
        };
        /**
         * AdminUserUpdate
         * @description Change an account's name or e-mail address (the role cannot change).
         */
        AdminUserUpdate: {
            /** Name */
            name?: string | null;
            /** Email */
            email?: string | null;
        };
        /** AdvocateOut */
        AdvocateOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string | null;
            /** Issample */
            isSample: boolean;
        };
        /** AnalysisContradictionOut */
        AnalysisContradictionOut: {
            /** Id */
            id: string;
            /** Description */
            description: string;
            /**
             * Sources
             * @description At least two verified sources.
             */
            sources: components["schemas"]["AnalysisSourceOut"][];
        };
        /** AnalysisDocumentOut */
        AnalysisDocumentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Eligible
             * @description Its text is ready, so it can be analysed.
             */
            eligible: boolean;
            /** Sectioncount */
            sectionCount: number | null;
            /** Pagecount */
            pageCount: number | null;
        };
        /** AnalysisEvidenceSummaryOut */
        AnalysisEvidenceSummaryOut: {
            /**
             * Documents
             * @description Documents whose passages were sent.
             */
            documents: number;
            /** Passages */
            passages: number;
            /** Judgmentpassages */
            judgmentPassages: number;
            /**
             * Characters
             * @description Characters of case and judgment text sent.
             */
            characters: number;
            /**
             * Truncated
             * @description True when limits left some passages out.
             */
            truncated: boolean;
        };
        /** AnalysisFactOut */
        AnalysisFactOut: {
            /** Id */
            id: string;
            /**
             * Statement
             * @description The model's wording; supported by the quoted source.
             */
            statement: string;
            source: components["schemas"]["AnalysisSourceOut"];
        };
        /** AnalysisIssueOut */
        AnalysisIssueOut: {
            /** Id */
            id: string;
            /** Question */
            question: string;
            /**
             * Factids
             * @description Facts of this result the issue rests on.
             */
            factIds: string[];
        };
        /** AnalysisLimitsOut */
        AnalysisLimitsOut: {
            /** Maxdocuments */
            maxDocuments: number;
            /** Maxinputchars */
            maxInputChars: number;
            /** Maxprecedents */
            maxPrecedents: number;
            /** Runsperhour */
            runsPerHour: number;
        };
        /** AnalysisPassageRefOut */
        AnalysisPassageRefOut: {
            /**
             * Chunkid
             * Format: uuid
             */
            chunkId: string;
            /** Sectionnumber */
            sectionNumber: number;
            /** Pagenumber */
            pageNumber: number | null;
        };
        /**
         * AnalysisPrecedentOut
         * @description A comparison with a judgment passage that was retrieved for this run.
         */
        AnalysisPrecedentOut: {
            /** Id */
            id: string;
            /**
             * Evidenceid
             * @description e.g. 'J1'.
             */
            evidenceId: string;
            /**
             * Judgmentid
             * Format: uuid
             */
            judgmentId: string;
            /** Title */
            title: string;
            /** Court */
            court: string;
            /** Citation */
            citation: string | null;
            /** Year */
            year: number | null;
            /**
             * Synthetic
             * @description Invented test judgment: never to be cited.
             */
            synthetic: boolean;
            /**
             * Retrievalrank
             * @description Its rank in the keyword retrieval (1 = first).
             */
            retrievalRank: number;
            passage: components["schemas"]["AnalysisPassageRefOut"];
            /**
             * Summary
             * @description What the judgment passage says (the model's summary).
             */
            summary: string;
            /** Similarities */
            similarities: string[];
            /** Differences */
            differences: string[];
        };
        /**
         * AnalysisRemovedOut
         * @description What validation removed from the model's answer, and why.
         */
        AnalysisRemovedOut: {
            /** Count */
            count: number;
            /** Reasons */
            reasons: components["schemas"]["AnalysisRemovedReasonOut"][];
        };
        /** AnalysisRemovedReasonOut */
        AnalysisRemovedReasonOut: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Count */
            count: number;
        };
        /** AnalysisResultOut */
        AnalysisResultOut: {
            /** Facts */
            facts: components["schemas"]["AnalysisFactOut"][];
            /** Issues */
            issues: components["schemas"]["AnalysisIssueOut"][];
            /** Precedents */
            precedents: components["schemas"]["AnalysisPrecedentOut"][];
            /** Contradictions */
            contradictions: components["schemas"]["AnalysisContradictionOut"][];
            /**
             * Insufficientevidence
             * @description True when the evidence did not support a useful analysis.
             */
            insufficientEvidence: boolean;
            /** Insufficientreason */
            insufficientReason: string | null;
            /**
             * Precedentsavailable
             * @description False when no judgment passage was available to compare with.
             */
            precedentsAvailable: boolean;
            removed: components["schemas"]["AnalysisRemovedOut"];
        };
        /** AnalysisRunIn */
        AnalysisRunIn: {
            /**
             * Documentids
             * @description Documents of this case to analyse.
             */
            documentIds: string[];
            /**
             * Confirmtransmission
             * @description Must be true: the user confirms the selected text is sent to the provider.
             */
            confirmTransmission: boolean;
        };
        /** AnalysisRunListOut */
        AnalysisRunListOut: {
            /** Items */
            items: components["schemas"]["AnalysisRunSummaryOut"][];
        };
        /** AnalysisRunOut */
        AnalysisRunOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Caseid
             * Format: uuid
             */
            caseId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "ready" | "failed";
            /** Reasoncode */
            reasonCode: string | null;
            /** Reason */
            reason: string | null;
            /**
             * Provider
             * @description 'gemini' (Google Gemini API) or 'scripted' (test double).
             */
            provider: string;
            /** Model */
            model: string;
            /** Promptversion */
            promptVersion: string;
            requestedBy: components["schemas"]["ActorOut"] | null;
            /**
             * Documentcount
             * @description Documents selected for the run.
             */
            documentCount: number;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Startedat */
            startedAt: string | null;
            /** Finishedat */
            finishedAt: string | null;
            evidence: components["schemas"]["AnalysisEvidenceSummaryOut"] | null;
            /** @description Only for status 'ready'. */
            result: components["schemas"]["AnalysisResultOut"] | null;
        };
        /** AnalysisRunSummaryOut */
        AnalysisRunSummaryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Caseid
             * Format: uuid
             */
            caseId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "ready" | "failed";
            /** Reasoncode */
            reasonCode: string | null;
            /** Reason */
            reason: string | null;
            /**
             * Provider
             * @description 'gemini' (Google Gemini API) or 'scripted' (test double).
             */
            provider: string;
            /** Model */
            model: string;
            /** Promptversion */
            promptVersion: string;
            requestedBy: components["schemas"]["ActorOut"] | null;
            /**
             * Documentcount
             * @description Documents selected for the run.
             */
            documentCount: number;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Startedat */
            startedAt: string | null;
            /** Finishedat */
            finishedAt: string | null;
        };
        /**
         * AnalysisSetupOut
         * @description Whether this case can be analysed now, and what would be sent where.
         */
        AnalysisSetupOut: {
            /**
             * Available
             * @description Analysis is configured on this server.
             */
            available: boolean;
            /** Unavailablereason */
            unavailableReason: string | null;
            /**
             * Provider
             * @description Null when analysis is not configured.
             */
            provider: string | null;
            /**
             * Providerlabel
             * @description e.g. 'Google Gemini API'.
             */
            providerLabel: string | null;
            /** Model */
            model: string | null;
            /** Promptversion */
            promptVersion: string;
            /**
             * Canrun
             * @description This user may start an analysis on this case now.
             */
            canRun: boolean;
            /** Cannotrunreason */
            cannotRunReason: string | null;
            /**
             * Sampleonly
             * @description Only sample (fictional) cases may be analysed on this server.
             */
            sampleOnly: boolean;
            /** Caseissample */
            caseIsSample: boolean;
            /** Documents */
            documents: components["schemas"]["AnalysisDocumentOut"][];
            /**
             * Judgmentsavailable
             * @description Judgments in the collection (0 = none).
             */
            judgmentsAvailable: number;
            limits: components["schemas"]["AnalysisLimitsOut"];
            /** Activerunid */
            activeRunId: string | null;
        };
        /**
         * AnalysisSourceOut
         * @description A passage of one of the case's documents that supports an item, with the
         *     verified quote.
         */
        AnalysisSourceOut: {
            /**
             * Evidenceid
             * @description The passage's id in this run's evidence, e.g. 'D3'.
             */
            evidenceId: string;
            /**
             * Documentid
             * Format: uuid
             */
            documentId: string;
            /** Documentname */
            documentName: string;
            /**
             * Chunkid
             * Format: uuid
             */
            chunkId: string;
            /**
             * Sectionnumber
             * @description The page (PDF) or part; links to the document text.
             */
            sectionNumber: number;
            /**
             * Pagenumber
             * @description The PDF page; null for documents without pages.
             */
            pageNumber: number | null;
            /**
             * Quote
             * @description Occurs verbatim in the passage (whitespace normalised).
             */
            quote: string;
        };
        /**
         * AuditEventOut
         * @description One audit-log entry. ``details`` holds only whitelisted, non-secret values.
         */
        AuditEventOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
            /** Actorid */
            actorId: string | null;
            /**
             * Actorname
             * @description As it was when the event happened.
             */
            actorName: string | null;
            /** Actorrole */
            actorRole: string | null;
            /** Action */
            action: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "success" | "denied" | "failed";
            /** Targettype */
            targetType: string | null;
            /** Targetid */
            targetId: string | null;
            /** Caseid */
            caseId: string | null;
            /** Casenumber */
            caseNumber: string | null;
            /** Details */
            details: {
                [key: string]: unknown;
            };
        };
        /** AuditPage */
        AuditPage: {
            /** Events */
            events: components["schemas"]["AuditEventOut"][];
            /**
             * Nextbefore
             * @description Pass as ``before`` for the next (older) page; null on the last page.
             */
            nextBefore: string | null;
        };
        /** CaseCreate */
        CaseCreate: {
            /** Title */
            title: string;
            /**
             * Clientid
             * Format: uuid
             */
            clientId: string;
            /**
             * Practicearea
             * @enum {string}
             */
            practiceArea: "Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour";
            /**
             * Status
             * @enum {string}
             */
            status: "Open" | "In Progress" | "On Hold" | "Closed";
            /**
             * Priority
             * @enum {string}
             */
            priority: "Low" | "Medium" | "High" | "Critical";
            /**
             * Leadadvocateid
             * Format: uuid
             */
            leadAdvocateId: string;
            /** Courtname */
            courtName?: string | null;
            /** Opposingparty */
            opposingParty?: string | null;
            /** Description */
            description: string;
            /**
             * Nexthearing
             * @description Creates the first hearing. Cannot be in the past.
             */
            nextHearing?: string | null;
        };
        /** CaseDetail */
        CaseDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Casenumber */
            caseNumber: string;
            /** Title */
            title: string;
            /**
             * Status
             * @enum {string}
             */
            status: "Open" | "In Progress" | "On Hold" | "Closed";
            /**
             * Priority
             * @enum {string}
             */
            priority: "Low" | "Medium" | "High" | "Critical";
            /**
             * Practicearea
             * @enum {string}
             */
            practiceArea: "Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour";
            /**
             * Clientid
             * Format: uuid
             */
            clientId: string;
            /** Clientname */
            clientName: string;
            /**
             * Leadadvocateid
             * Format: uuid
             */
            leadAdvocateId: string;
            /**
             * Leadattorney
             * @description Name of the lead advocate.
             */
            leadAttorney: string;
            /** Courtname */
            courtName: string | null;
            /** Opposingparty */
            opposingParty: string | null;
            /**
             * Openedon
             * Format: date
             */
            openedOn: string;
            /**
             * Nexthearing
             * @description Earliest hearing on or after today; if none, the most recent past one (so the client can show it has passed). Derived from the hearings.
             */
            nextHearing: string | null;
            /** Documentcount */
            documentCount: number;
            /**
             * Archivedat
             * @description When the case was archived (read-only until restored); null if active.
             */
            archivedAt: string | null;
            /** Issample */
            isSample: boolean;
            /** Description */
            description: string;
            /** Documents */
            documents: components["schemas"]["DocumentOut"][];
            /** Hearings */
            hearings: components["schemas"]["HearingOut"][];
            /** Timeline */
            timeline: components["schemas"]["TimelineEventOut"][];
            /** Team */
            team: components["schemas"]["TeamMemberOut"][];
            permissions: components["schemas"]["CasePermissions"];
        };
        /**
         * CasePermissions
         * @description What the signed-in user may do on this case (to show the right controls).
         *
         *     A convenience for the screens only: the server checks every action again.
         */
        CasePermissions: {
            /**
             * Relation
             * @enum {string}
             */
            relation: "admin" | "lead" | "associate" | "paralegal" | "client" | "none";
            /**
             * Editablefields
             * @description Fields this user may change (camelCase).
             */
            editableFields: string[];
            /** Canchangestatus */
            canChangeStatus: boolean;
            /** Canmanageteam */
            canManageTeam: boolean;
            /** Canarchive */
            canArchive: boolean;
            /** Canmanagehearings */
            canManageHearings: boolean;
            /** Canuploaddocuments */
            canUploadDocuments: boolean;
            /** Candeletedocuments */
            canDeleteDocuments: boolean;
            /** Canrestoredocuments */
            canRestoreDocuments: boolean;
            /** Cansharedocuments */
            canShareDocuments: boolean;
            /** Canrunanalysis */
            canRunAnalysis: boolean;
        };
        /**
         * CaseSearchHitOut
         * @description A passage of one of the case's documents, located exactly.
         */
        CaseSearchHitOut: {
            /**
             * Documentid
             * Format: uuid
             */
            documentId: string;
            /** Documentname */
            documentName: string;
            /**
             * Chunkid
             * Format: uuid
             */
            chunkId: string;
            /** Chunknumber */
            chunkNumber: number;
            /**
             * Sectionnumber
             * @description The page (PDF) or part the passage is in.
             */
            sectionNumber: number;
            /**
             * Pagenumber
             * @description The PDF page; null for documents without pages.
             */
            pageNumber: number | null;
            /**
             * Charstart
             * @description Offset of the passage in the section's extracted text.
             */
            charStart: number;
            /** Charend */
            charEnd: number;
            /**
             * Text
             * @description The passage, exactly as extracted.
             */
            text: string;
            /**
             * Score
             * @description Ranking score of the mode: cosine similarity (semantic), full-text rank (keyword) or reciprocal-rank fusion (hybrid). Higher is closer; not a probability.
             */
            score: number;
        };
        /**
         * CaseSearchOut
         * @description Passages of the case's own documents ranked against the query (no legal judgment).
         */
        CaseSearchOut: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "keyword" | "semantic" | "hybrid";
            /**
             * Model
             * @description The embedding model (semantic and hybrid modes).
             */
            model: string | null;
            /**
             * Documentswithtext
             * @description Live documents of the case whose text is ready.
             */
            documentsWithText: number;
            /**
             * Documentsindexed
             * @description Of those, how many have vectors for the model (semantic and hybrid).
             */
            documentsIndexed: number;
            /** Results */
            results: components["schemas"]["CaseSearchHitOut"][];
        };
        /** CaseSummary */
        CaseSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Casenumber */
            caseNumber: string;
            /** Title */
            title: string;
            /**
             * Status
             * @enum {string}
             */
            status: "Open" | "In Progress" | "On Hold" | "Closed";
            /**
             * Priority
             * @enum {string}
             */
            priority: "Low" | "Medium" | "High" | "Critical";
            /**
             * Practicearea
             * @enum {string}
             */
            practiceArea: "Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour";
            /**
             * Clientid
             * Format: uuid
             */
            clientId: string;
            /** Clientname */
            clientName: string;
            /**
             * Leadadvocateid
             * Format: uuid
             */
            leadAdvocateId: string;
            /**
             * Leadattorney
             * @description Name of the lead advocate.
             */
            leadAttorney: string;
            /** Courtname */
            courtName: string | null;
            /** Opposingparty */
            opposingParty: string | null;
            /**
             * Openedon
             * Format: date
             */
            openedOn: string;
            /**
             * Nexthearing
             * @description Earliest hearing on or after today; if none, the most recent past one (so the client can show it has passed). Derived from the hearings.
             */
            nextHearing: string | null;
            /** Documentcount */
            documentCount: number;
            /**
             * Archivedat
             * @description When the case was archived (read-only until restored); null if active.
             */
            archivedAt: string | null;
            /** Issample */
            isSample: boolean;
        };
        /**
         * CaseUpdate
         * @description Partial update. Only the fields present in the request change.
         *
         *     ``courtName`` and ``opposingParty`` may be null to clear them; the other
         *     fields cannot be null.
         */
        CaseUpdate: {
            /** Title */
            title?: string | null;
            /** Status */
            status?: ("Open" | "In Progress" | "On Hold" | "Closed") | null;
            /** Priority */
            priority?: ("Low" | "Medium" | "High" | "Critical") | null;
            /** Practicearea */
            practiceArea?: ("Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour") | null;
            /** Clientid */
            clientId?: string | null;
            /** Leadadvocateid */
            leadAdvocateId?: string | null;
            /** Courtname */
            courtName?: string | null;
            /** Opposingparty */
            opposingParty?: string | null;
            /** Description */
            description?: string | null;
        };
        /** ClientDetail */
        ClientDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string;
            /** Phone */
            phone: string;
            /** Company */
            company: string | null;
            /** Issample */
            isSample: boolean;
            /**
             * Cases
             * @description The client's cases that you may see.
             */
            cases: components["schemas"]["CaseSummary"][];
            /**
             * Canedit
             * @description Whether you may change these details.
             */
            canEdit: boolean;
        };
        /**
         * ClientIn
         * @description A new client. Name, e-mail and phone are required; the company is optional.
         */
        ClientIn: {
            /** Name */
            name: string;
            /** Email */
            email: string;
            /** Phone */
            phone: string;
            /** Company */
            company?: string | null;
        };
        /**
         * ClientOption
         * @description A client as offered in the new-case form: no contact details.
         */
        ClientOption: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Issample */
            isSample: boolean;
        };
        /** ClientOut */
        ClientOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string;
            /** Phone */
            phone: string;
            /** Company */
            company: string | null;
            /** Issample */
            isSample: boolean;
        };
        /**
         * ClientUpdate
         * @description Change a client's details. Only the fields present change; ``company`` may be null.
         */
        ClientUpdate: {
            /** Name */
            name?: string | null;
            /** Email */
            email?: string | null;
            /** Phone */
            phone?: string | null;
            /** Company */
            company?: string | null;
        };
        /**
         * DeletedDocumentOut
         * @description A deleted document, kept until restored or purged by an operator.
         */
        DeletedDocumentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Type */
            type: string;
            /**
             * Uploadedon
             * Format: date
             */
            uploadedOn: string;
            /**
             * Size
             * @description Human-readable size, e.g. '512 KB'.
             */
            size: string;
            /**
             * Sizebytes
             * @description Exact size of the stored file; null without one.
             */
            sizeBytes: number | null;
            /**
             * Hasfile
             * @description False for sample records, which have no stored file.
             */
            hasFile: boolean;
            /** Contenttype */
            contentType: string | null;
            /** Downloadurl */
            downloadUrl: string | null;
            /** @description Who uploaded it; null for sample records and earlier uploads. */
            uploadedBy: components["schemas"]["ActorOut"] | null;
            /**
             * Sharedwithclientat
             * @description When it was shared with the client (their portal shows it); null if not.
             */
            sharedWithClientAt: string | null;
            /** @description Text extraction; null for records without a stored file. */
            processing: components["schemas"]["DocumentProcessingOut"] | null;
            /** Issample */
            isSample: boolean;
            /**
             * Deletedat
             * Format: date-time
             */
            deletedAt: string;
            /** @description Who deleted it, if still known. */
            deletedBy: components["schemas"]["ActorOut"] | null;
        };
        /** DocumentOut */
        DocumentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Type */
            type: string;
            /**
             * Uploadedon
             * Format: date
             */
            uploadedOn: string;
            /**
             * Size
             * @description Human-readable size, e.g. '512 KB'.
             */
            size: string;
            /**
             * Sizebytes
             * @description Exact size of the stored file; null without one.
             */
            sizeBytes: number | null;
            /**
             * Hasfile
             * @description False for sample records, which have no stored file.
             */
            hasFile: boolean;
            /** Contenttype */
            contentType: string | null;
            /** Downloadurl */
            downloadUrl: string | null;
            /** @description Who uploaded it; null for sample records and earlier uploads. */
            uploadedBy: components["schemas"]["ActorOut"] | null;
            /**
             * Sharedwithclientat
             * @description When it was shared with the client (their portal shows it); null if not.
             */
            sharedWithClientAt: string | null;
            /** @description Text extraction; null for records without a stored file. */
            processing: components["schemas"]["DocumentProcessingOut"] | null;
            /** Issample */
            isSample: boolean;
        };
        /**
         * DocumentProcessingOut
         * @description Text extraction of a stored document (Phase 3).
         */
        DocumentProcessingOut: {
            /**
             * Status
             * @description queued, processing, ready, failed (with a reason) or unsupported.
             * @enum {string}
             */
            status: "queued" | "processing" | "ready" | "failed" | "unsupported";
            /**
             * Reasoncode
             * @description Why it failed or is unsupported.
             */
            reasonCode: string | null;
            /** Reason */
            reason: string | null;
            /**
             * Pagecount
             * @description PDFs only; null for documents without pages.
             */
            pageCount: number | null;
            /**
             * Sectioncount
             * @description Pages, or parts of a document without pages.
             */
            sectionCount: number | null;
            /** Chunkcount */
            chunkCount: number | null;
            /**
             * Indexstatus
             * @description Search indexing (embeddings): disabled unless configured.
             * @enum {string}
             */
            indexStatus: "disabled" | "pending" | "indexed" | "failed";
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /**
         * DocumentTextOut
         * @description One page (or part) of a document's extracted text.
         */
        DocumentTextOut: {
            /**
             * Documentid
             * Format: uuid
             */
            documentId: string;
            /** Documentname */
            documentName: string;
            /**
             * Extractor
             * @description What extracted the text, e.g. 'pypdf 6.21.1'.
             */
            extractor: string | null;
            /**
             * Pagecount
             * @description PDFs only; null for documents without pages.
             */
            pageCount: number | null;
            /** Sectioncount */
            sectionCount: number;
            /** Charcount */
            charCount: number;
            /** Extractedat */
            extractedAt: string | null;
            section: components["schemas"]["DocumentTextSectionOut"];
        };
        /** DocumentTextSectionOut */
        DocumentTextSectionOut: {
            /**
             * Number
             * @description 1 to sectionCount.
             */
            number: number;
            /**
             * Pagenumber
             * @description The PDF page; null for documents without pages.
             */
            pageNumber: number | null;
            /**
             * Text
             * @description Exactly as extracted; may be empty for a page without text.
             */
            text: string;
            /** Chunkcount */
            chunkCount: number;
        };
        /**
         * FieldError
         * @description One invalid field. ``field`` uses the request's camelCase name.
         */
        FieldError: {
            /** Field */
            field: string;
            /** Message */
            message: string;
        };
        /** Health */
        Health: {
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "unavailable";
            /**
             * Database
             * @enum {string}
             */
            database: "ok" | "unavailable";
        };
        /** HearingCancelIn */
        HearingCancelIn: {
            /**
             * Reason
             * @description Optional, shown on the case.
             */
            reason?: string | null;
        };
        /**
         * HearingIn
         * @description Schedule a hearing. The time may be left out until the court lists it.
         */
        HearingIn: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Time
             * @description 24-hour HH:MM, or omitted.
             */
            time?: string | null;
            /** Court */
            court: string;
            /** Purpose */
            purpose: string;
        };
        /** HearingOut */
        HearingOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Time
             * @description 24-hour HH:MM, or null until the court lists it.
             */
            time: string | null;
            /** Court */
            court: string;
            /** Purpose */
            purpose: string;
            /**
             * Status
             * @description Cancelled hearings are kept but are never the next or an upcoming hearing.
             * @enum {string}
             */
            status: "Scheduled" | "Cancelled";
            /** Cancellationreason */
            cancellationReason: string | null;
            /** Issample */
            isSample: boolean;
        };
        /**
         * HearingSchedule
         * @description Hearings in a date range, soonest first.
         */
        HearingSchedule: {
            /** Hearings */
            hearings: components["schemas"]["ScheduledHearingOut"][];
            /**
             * Truncated
             * @description True when more hearings matched than the limit.
             */
            truncated: boolean;
        };
        /**
         * HearingUpdate
         * @description Change a scheduled hearing. Only the fields present change; ``time`` may be null.
         */
        HearingUpdate: {
            /** Date */
            date?: string | null;
            /** Time */
            time?: string | null;
            /** Court */
            court?: string | null;
            /** Purpose */
            purpose?: string | null;
        };
        /** JudgmentDetailOut */
        JudgmentDetailOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            /** Court */
            court: string;
            /**
             * Citation
             * @description Only when the source supplied one.
             */
            citation: string | null;
            /** Decisiondate */
            decisionDate: string | null;
            /** Year */
            year: number | null;
            /** Practiceareas */
            practiceAreas: string[];
            /** Sourcename */
            sourceName: string;
            /**
             * Sourceurl
             * @description The judgment at its source (https).
             */
            sourceUrl: string;
            /**
             * Synthetic
             * @description True for invented test data; never a real judgment, never to be cited.
             */
            synthetic: boolean;
            /** Bench */
            bench: string | null;
            source: components["schemas"]["JudgmentSourceOut"];
            /**
             * Pagecount
             * @description PDFs only.
             */
            pageCount: number | null;
            /** Sectioncount */
            sectionCount: number;
            /** Charcount */
            charCount: number;
            /** Extractor */
            extractor: string;
            /**
             * Importedat
             * Format: date-time
             */
            importedAt: string;
        };
        /**
         * JudgmentFacetsOut
         * @description What the collection holds, for filters and honest empty states.
         */
        JudgmentFacetsOut: {
            /** Total */
            total: number;
            /**
             * Synthetic
             * @description Invented test judgments among them.
             */
            synthetic: number;
            /**
             * Indexed
             * @description Judgments with vectors for the current model.
             */
            indexed: number;
            /** Courts */
            courts: string[];
            /** Yearmin */
            yearMin: number | null;
            /** Yearmax */
            yearMax: number | null;
            modes: components["schemas"]["JudgmentSearchModesOut"];
        };
        /** JudgmentHitOut */
        JudgmentHitOut: {
            judgment: components["schemas"]["JudgmentSummaryOut"];
            /**
             * Score
             * @description Ranking score of the mode (full-text rank, cosine similarity or reciprocal-rank fusion). Higher ranks first; not a probability or a legal opinion.
             */
            score: number;
            passage: components["schemas"]["JudgmentPassageOut"];
        };
        /** JudgmentPageOut */
        JudgmentPageOut: {
            /** Items */
            items: components["schemas"]["JudgmentSummaryOut"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
        };
        /** JudgmentPassageOut */
        JudgmentPassageOut: {
            /**
             * Chunkid
             * Format: uuid
             */
            chunkId: string;
            /**
             * Sectionnumber
             * @description The page (PDF) or part the passage is in.
             */
            sectionNumber: number;
            /** Pagenumber */
            pageNumber: number | null;
            /**
             * Charstart
             * @description Offset of the passage in the section's text.
             */
            charStart: number;
            /** Charend */
            charEnd: number;
            /**
             * Text
             * @description The passage, exactly as extracted.
             */
            text: string;
        };
        /** JudgmentSearchModesOut */
        JudgmentSearchModesOut: {
            /** Keyword */
            keyword: boolean;
            /** Semantic */
            semantic: boolean;
            /** Hybrid */
            hybrid: boolean;
            /**
             * Unavailablereason
             * @description Why semantic and hybrid are off.
             */
            unavailableReason: string | null;
            /** Model */
            model: string | null;
        };
        /**
         * JudgmentSearchOut
         * @description Judgments of the collection ranked by their best matching passage.
         */
        JudgmentSearchOut: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "keyword" | "semantic" | "hybrid";
            /**
             * Model
             * @description The embedding model (semantic and hybrid modes).
             */
            model: string | null;
            /**
             * Total
             * @description Judgments ranked (at most maxResults).
             */
            total: number;
            /** Maxresults */
            maxResults: number;
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Results */
            results: components["schemas"]["JudgmentHitOut"][];
        };
        /** JudgmentSourceOut */
        JudgmentSourceOut: {
            /** Key */
            key: string;
            /** Name */
            name: string;
            /** Termsurl */
            termsUrl: string;
            /**
             * Termscheckedon
             * Format: date
             */
            termsCheckedOn: string;
            /** Termscheckedby */
            termsCheckedBy: string;
            /**
             * Permitteduse
             * @description What the source's terms allow, as recorded.
             */
            permittedUse: string;
            /** Synthetic */
            synthetic: boolean;
        };
        /**
         * JudgmentSummaryOut
         * @description A judgment in the collection, with the metadata its import supplied.
         */
        JudgmentSummaryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            /** Court */
            court: string;
            /**
             * Citation
             * @description Only when the source supplied one.
             */
            citation: string | null;
            /** Decisiondate */
            decisionDate: string | null;
            /** Year */
            year: number | null;
            /** Practiceareas */
            practiceAreas: string[];
            /** Sourcename */
            sourceName: string;
            /**
             * Sourceurl
             * @description The judgment at its source (https).
             */
            sourceUrl: string;
            /**
             * Synthetic
             * @description True for invented test data; never a real judgment, never to be cited.
             */
            synthetic: boolean;
        };
        /** JudgmentTextOut */
        JudgmentTextOut: {
            /**
             * Judgmentid
             * Format: uuid
             */
            judgmentId: string;
            /** Title */
            title: string;
            /** Synthetic */
            synthetic: boolean;
            /** Pagecount */
            pageCount: number | null;
            /** Sectioncount */
            sectionCount: number;
            section: components["schemas"]["JudgmentTextSectionOut"];
        };
        /** JudgmentTextSectionOut */
        JudgmentTextSectionOut: {
            /** Number */
            number: number;
            /** Pagenumber */
            pageNumber: number | null;
            /** Text */
            text: string;
        };
        /**
         * MeOut
         * @description The signed-in user. Never includes password or session details.
         */
        MeOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Email */
            email: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "Administrator" | "Advocate" | "Paralegal" | "Client";
            /**
             * Clientid
             * @description For Client users: the client record they represent.
             */
            clientId: string | null;
            /**
             * Mustchangepassword
             * @description True while a temporary password must be replaced before anything else.
             */
            mustChangePassword: boolean;
        };
        /** PasswordChangeIn */
        PasswordChangeIn: {
            /** Currentpassword */
            currentPassword: string;
            /** Newpassword */
            newPassword: string;
        };
        /** PortalCaseDetail */
        PortalCaseDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Casenumber */
            caseNumber: string;
            /** Title */
            title: string;
            /**
             * Status
             * @enum {string}
             */
            status: "Open" | "In Progress" | "On Hold" | "Closed";
            /**
             * Practicearea
             * @enum {string}
             */
            practiceArea: "Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour";
            /** Leadattorney */
            leadAttorney: string;
            /** Courtname */
            courtName: string | null;
            /**
             * Openedon
             * Format: date
             */
            openedOn: string;
            /** Nexthearing */
            nextHearing: string | null;
            /**
             * Hearings
             * @description Scheduled hearings from today on.
             */
            hearings: components["schemas"]["PortalHearingOut"][];
            /**
             * Documents
             * @description Documents shared with you.
             */
            documents: components["schemas"]["PortalDocumentOut"][];
        };
        /**
         * PortalCaseSummary
         * @description A case as its client sees it: no internal notes, priority or team.
         */
        PortalCaseSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Casenumber */
            caseNumber: string;
            /** Title */
            title: string;
            /**
             * Status
             * @enum {string}
             */
            status: "Open" | "In Progress" | "On Hold" | "Closed";
            /**
             * Practicearea
             * @enum {string}
             */
            practiceArea: "Corporate / Commercial" | "Civil" | "Criminal" | "Family" | "Intellectual Property" | "Constitutional / Administrative" | "Real Estate" | "Employment & Labour";
            /** Leadattorney */
            leadAttorney: string;
            /** Courtname */
            courtName: string | null;
            /**
             * Openedon
             * Format: date
             */
            openedOn: string;
            /** Nexthearing */
            nextHearing: string | null;
        };
        /**
         * PortalDocumentOut
         * @description A document shared with the client.
         */
        PortalDocumentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Type */
            type: string;
            /** Size */
            size: string;
            /**
             * Sharedon
             * Format: date
             */
            sharedOn: string;
            /** Downloadurl */
            downloadUrl: string;
        };
        /**
         * PortalHearingOut
         * @description A scheduled hearing as the client sees it.
         */
        PortalHearingOut: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Time */
            time: string | null;
            /** Court */
            court: string;
            /** Purpose */
            purpose: string;
        };
        /**
         * Problem
         * @description RFC 9457 problem details, plus LexFlow's ``code`` and ``errors`` members.
         */
        Problem: {
            /**
             * Type
             * @description URI identifying the problem type.
             */
            type: string;
            /** Title */
            title: string;
            /** Status */
            status: number;
            /** Detail */
            detail?: string | null;
            /**
             * Code
             * @description Stable machine-readable reason, e.g. 'duplicate'.
             */
            code?: string | null;
            /** Errors */
            errors?: components["schemas"]["FieldError"][];
        };
        /** ScheduledHearingOut */
        ScheduledHearingOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Time
             * @description 24-hour HH:MM, or null until the court lists it.
             */
            time: string | null;
            /** Court */
            court: string;
            /** Purpose */
            purpose: string;
            /**
             * Status
             * @description Cancelled hearings are kept but are never the next or an upcoming hearing.
             * @enum {string}
             */
            status: "Scheduled" | "Cancelled";
            /** Cancellationreason */
            cancellationReason: string | null;
            /** Issample */
            isSample: boolean;
            /**
             * Caseid
             * Format: uuid
             */
            caseId: string;
            /** Casetitle */
            caseTitle: string;
            /** Casenumber */
            caseNumber: string;
            /**
             * Leadattorney
             * @description Name of the case's lead advocate.
             */
            leadAttorney: string;
        };
        /** SignInIn */
        SignInIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * StaffOut
         * @description An active staff member, as offered when building a case team.
         */
        StaffOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Role
             * @enum {string}
             */
            role: "Administrator" | "Advocate" | "Paralegal" | "Client";
        };
        /** TeamMemberIn */
        TeamMemberIn: {
            /**
             * Userid
             * Format: uuid
             * @description An active Advocate (associate) or Paralegal.
             */
            userId: string;
        };
        /**
         * TeamMemberOut
         * @description Someone on a case team besides the lead advocate.
         */
        TeamMemberOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Role
             * @enum {string}
             */
            role: "Administrator" | "Advocate" | "Paralegal" | "Client";
            /**
             * Memberrole
             * @enum {string}
             */
            memberRole: "associate" | "paralegal";
        };
        /** TemporaryPasswordIn */
        TemporaryPasswordIn: {
            /** Temporarypassword */
            temporaryPassword: string;
        };
        /** TimelineEventOut */
        TimelineEventOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Label */
            label: string;
            /** Description */
            description: string;
            /** @description Who made the change. Null for sample entries and changes made by the system. */
            actor: components["schemas"]["ActorOut"] | null;
            /**
             * Recordedat
             * Format: date-time
             * @description When the entry was recorded (UTC).
             */
            recordedAt: string;
            /** Issample */
            isSample: boolean;
        };
        /** UpcomingHearingOut */
        UpcomingHearingOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Time
             * @description 24-hour HH:MM, or null until the court lists it.
             */
            time: string | null;
            /** Court */
            court: string;
            /** Purpose */
            purpose: string;
            /**
             * Status
             * @description Cancelled hearings are kept but are never the next or an upcoming hearing.
             * @enum {string}
             */
            status: "Scheduled" | "Cancelled";
            /** Cancellationreason */
            cancellationReason: string | null;
            /** Issample */
            isSample: boolean;
            /**
             * Caseid
             * Format: uuid
             */
            caseId: string;
            /** Casetitle */
            caseTitle: string;
            /** Casenumber */
            caseNumber: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
            /** @description The database is not reachable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignInIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    change_password_api_auth_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChangeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_clients_api_clients_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"][];
                };
            };
        };
    };
    create_client_api_clients_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    client_options_api_clients_options_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOption"][];
                };
            };
        };
    };
    list_staff_api_staff_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffOut"][];
                };
            };
        };
    };
    list_advocates_api_advocates_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdvocateOut"][];
                };
            };
        };
    };
    get_client_api_clients__client_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientDetail"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    update_client_api_clients__client_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_cases_api_cases_get: {
        parameters: {
            query?: {
                /** @description Archived cases: leave out (default), include, or only. */
                archived?: "exclude" | "include" | "only";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseSummary"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    create_case_api_cases_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CaseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_case_api_cases__case_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    update_case_api_cases__case_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CaseUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    archive_case_api_cases__case_id__archive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    unarchive_case_api_cases__case_id__unarchive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    add_team_member_api_cases__case_id__team_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TeamMemberIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    remove_team_member_api_cases__case_id__team__member_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
                member_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    upcoming_hearings_api_hearings_upcoming_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UpcomingHearingOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_documents_api_cases__case_id__documents_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"][];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    upload_document_api_cases__case_id__documents_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": {
                    /**
                     * Format: binary
                     * @description One file: PDF, Word, text, PNG, JPG, GIF or WebP.
                     */
                    file: string;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unsupported Media Type */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    read_document_text_api_documents__document_id__text_get: {
        parameters: {
            query?: {
                /** @description The page (PDF) or part to read. */
                section?: number;
            };
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentTextOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    reprocess_document_api_documents__document_id__reprocess_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    download_document_api_documents__document_id__download_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The stored file. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": unknown;
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    delete_document_api_documents__document_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    share_document_api_documents__document_id__share_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    unshare_document_api_documents__document_id__unshare_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_deleted_documents_api_cases__case_id__documents_deleted_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeletedDocumentOut"][];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    restore_document_api_documents__document_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    search_case_api_cases__case_id__search_get: {
        parameters: {
            query: {
                /** @description What to look for. */
                q: string;
                /** @description keyword (full text), semantic (embeddings) or hybrid. */
                mode?: "keyword" | "semantic" | "hybrid";
                limit?: number;
            };
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseSearchOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    analysis_setup_api_cases__case_id__analysis_setup_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisSetupOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_analyses_api_cases__case_id__analysis_runs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRunListOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    start_analysis_api_cases__case_id__analysis_runs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalysisRunIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRunOut"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": unknown;
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_analysis_api_cases__case_id__analysis_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRunOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    judgment_facets_api_judgments_facets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JudgmentFacetsOut"];
                };
            };
        };
    };
    list_judgments_api_judgments_get: {
        parameters: {
            query?: {
                /** @description Only this court (exact name). */
                court?: string | null;
                yearFrom?: number | null;
                yearTo?: number | null;
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JudgmentPageOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    search_judgments_api_judgments_search_get: {
        parameters: {
            query: {
                /** @description What to look for. */
                q: string;
                mode?: "keyword" | "semantic" | "hybrid";
                /** @description Only this court (exact name). */
                court?: string | null;
                yearFrom?: number | null;
                yearTo?: number | null;
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JudgmentSearchOut"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_judgment_api_judgments__judgment_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                judgment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JudgmentDetailOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    judgment_text_api_judgments__judgment_id__text_get: {
        parameters: {
            query?: {
                /** @description The page (PDF) or part to read. */
                section?: number;
            };
            header?: never;
            path: {
                judgment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JudgmentTextOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    hearing_schedule_api_hearings_get: {
        parameters: {
            query?: {
                /** @description First day (default: today). */
                from?: string | null;
                /** @description Last day (default: 30 days after the first). */
                to?: string | null;
                includeCancelled?: boolean;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HearingSchedule"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    schedule_hearing_api_cases__case_id__hearings_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HearingIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    update_hearing_api_hearings__hearing_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                hearing_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HearingUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    cancel_hearing_api_hearings__hearing_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                hearing_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HearingCancelIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    read_audit_log_api_admin_audit_get: {
        parameters: {
            query?: {
                /** @description An action, or a prefix ending in a dot (``document.``). */
                action?: string | null;
                outcome?: ("success" | "denied" | "failed") | null;
                actorId?: string | null;
                caseId?: string | null;
                from?: string | null;
                to?: string | null;
                /** @description ``nextBefore`` of a page. */
                before?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditPage"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_users_api_admin_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"][];
                };
            };
        };
    };
    create_user_api_admin_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminUserCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    update_user_api_admin_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminUserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    disable_user_api_admin_users__user_id__disable_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    enable_user_api_admin_users__user_id__enable_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    unlock_user_api_admin_users__user_id__unlock_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    reset_password_api_admin_users__user_id__password_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemporaryPasswordIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_cases_api_portal_cases_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PortalCaseSummary"][];
                };
            };
        };
    };
    get_case_api_portal_cases__case_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PortalCaseDetail"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    download_document_api_portal_documents__document_id__download_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The shared file. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": unknown;
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
