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
    "/api/clients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Clients
         * @description All clients, by name.
         */
        get: operations["list_clients_api_clients_get"];
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
         * @description Users who can lead a case (role Advocate), by name.
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
    "/api/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Cases
         * @description Every case, newest first, with what the case list needs.
         */
        get: operations["list_cases_api_cases_get"];
        put?: never;
        /**
         * Create Case
         * @description Open a new case. The server assigns the case number and opening date.
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
         * @description One case with its documents, hearings and timeline.
         */
        get: operations["get_case_api_cases__case_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Case
         * @description Change some of a case's details. Any change adds a timeline entry.
         *
         *     Phase 1 has no sign-in, so the entry records no actor.
         */
        patch: operations["update_case_api_cases__case_id__patch"];
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
         * @description Hearings on or after today across all cases, soonest first.
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
         * @description Remove a document and its stored file.
         */
        delete: operations["delete_document_api_documents__document_id__delete"];
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
        /** Body_upload_document_api_cases__case_id__documents_post */
        Body_upload_document_api_cases__case_id__documents_post: {
            /**
             * File
             * @description One file: PDF, Word, text, PNG, JPG, GIF or WebP.
             */
            file: string;
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
            /** Issample */
            isSample: boolean;
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
            /** Issample */
            isSample: boolean;
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
            /** @description Who made the change. Null when no signed-in user did (always in Phase 1). */
            actor: components["schemas"]["ActorOut"] | null;
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
    list_cases_api_cases_get: {
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
                    "application/json": components["schemas"]["CaseSummary"][];
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
                "multipart/form-data": components["schemas"]["Body_upload_document_api_cases__case_id__documents_post"];
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
