import type { Problem } from '../../types';

/**
 * Low-level access to the LexFlow API.
 *
 * Every failure becomes an `ApiError`: an unreachable API (code 'network'), RFC 9457
 * problem responses (with `code` and per-field `fieldErrors`) and anything else.
 * Hooks and pages never call `fetch` directly.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  /**
   * HTTP status, or 0 when the request never got an answer. When the API is
   * unreachable `code` is 'network', whether or not a proxy answered for it.
   */
  readonly status: number;
  /** Stable reason from the server, e.g. 'duplicate' or 'case-not-found'. */
  readonly code: string | null;
  readonly title: string;
  /** Messages keyed by request field name, e.g. `{ title: '…' }`. */
  readonly fieldErrors: Record<string, string>;

  constructor(options: {
    status: number;
    code: string | null;
    title: string;
    detail: string;
    fieldErrors?: Record<string, string>;
  }) {
    super(options.detail);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.title = options.title;
    this.fieldErrors = options.fieldErrors ?? {};
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** The request itself was wrong (4xx): retrying won't help. */
  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

export function apiUrl(path: string): string {
  // Absolute, so the same code works in the browser and in Node-based tests.
  return new URL(`${BASE}${path}`, window.location.href).toString();
}

const unreachable = (status: number) =>
  new ApiError({
    status,
    code: 'network',
    title: 'Server unreachable',
    detail: "Can't reach the LexFlow server. Check that it is running, then try again.",
  });

async function toApiError(response: Response): Promise<ApiError> {
  let problem: Partial<Problem> | null = null;
  if (response.headers.get('content-type')?.includes('json')) {
    try {
      problem = (await response.json()) as Partial<Problem>;
    } catch {
      // not JSON after all; handled below
    }
  }
  // The API answers every error with a problem document. A server error without
  // one comes from something in between: the Vite proxy answers 500 with an
  // empty body when the API isn't running, and gateways answer 502-504.
  if (!problem && response.status >= 500) return unreachable(response.status);
  problem ??= {};
  return new ApiError({
    status: response.status,
    code: problem.code ?? null,
    title: problem.title ?? (response.statusText || 'Request failed'),
    detail: problem.detail ?? `The server answered with status ${response.status}.`,
    fieldErrors: Object.fromEntries((problem.errors ?? []).map((e) => [e.field, e.message])),
  });
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/**
 * Sign-in events any request can reveal: the session has ended (401
 * `not-authenticated`), or a temporary password must be replaced first. The
 * sign-in state listens and reacts (forgets cached data, routes the user).
 */
export type AuthEvent = 'unauthenticated' | 'password-change-required';

const authListeners = new Set<(event: AuthEvent) => void>();

export function onAuthEvent(listener: (event: AuthEvent) => void): () => void {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

function announce(error: ApiError) {
  const event: AuthEvent | null =
    error.status === 401 && error.code === 'not-authenticated'
      ? 'unauthenticated'
      : error.code === 'password-change-required'
        ? 'password-change-required'
        : null;
  if (event) authListeners.forEach((listener) => listener(event));
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      // The session cookie is HttpOnly: the browser attaches it, scripts never see it.
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        // Required by the API on every change (CSRF protection): a page on another
        // origin cannot add this header without a CORS preflight, which is never granted.
        ...(UNSAFE_METHODS.has(method) ? { 'X-LexFlow-Request': '1' } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw unreachable(0);
  }
  if (!response.ok) {
    const error = await toApiError(response);
    announce(error);
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** A file the server generated (for example a case brief), ready to save. */
export interface DownloadedFile {
  blob: Blob;
  filename: string;
}

/** The server's file name from Content-Disposition, made safe for saving. */
function attachmentName(header: string | null, fallback: string): string {
  const match = header ? /filename="?([^";]+)"?/i.exec(header) : null;
  const name = (match?.[1] ?? fallback).replace(/[^A-Za-z0-9._-]/g, '_');
  return name || fallback;
}

/** Like `apiFetch`, for a GET that answers with a file instead of JSON. */
export async function apiFetchFile(
  path: string,
  fallbackName = 'download',
): Promise<DownloadedFile> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { credentials: 'same-origin' });
  } catch {
    throw unreachable(0);
  }
  if (!response.ok) {
    const error = await toApiError(response);
    announce(error);
    throw error;
  }
  return {
    blob: await response.blob(),
    filename: attachmentName(response.headers.get('Content-Disposition'), fallbackName),
  };
}

/** A readable message for any error a query or mutation can raise. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return 'Something went wrong. Try again.';
}
