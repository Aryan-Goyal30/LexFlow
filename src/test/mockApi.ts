/**
 * A fake LexFlow API for front-end tests, mounted at the network boundary with
 * MSW. It mirrors the real server's contract (shapes from the generated
 * OpenAPI types, RFC 9457 problems with the same codes and messages) and keeps
 * its data in memory, rebuilt from the fictional sample data before each test.
 *
 * Tests that need a failure or a slow response override a route with
 * `server.use(...)`; see `problem()` and `delay` from msw.
 */

import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { advocates as sampleAdvocates, mockCases, mockClients } from '../data/mockData';
import { formatFileSize, todayIsoDate } from '../lib/format';
import { ACCEPTED_TYPES_LABEL } from '../lib/documentFiles';
import type {
  AdminUser,
  AdminUserChanges,
  AdminUserInput,
  AuditEvent,
  Advocate,
  Case,
  CaseChanges,
  CaseDocument,
  CaseSummary,
  DeletedDocument,
  DocumentProcessing,
  HearingChanges,
  HearingInput,
  Client,
  ClientChanges,
  ClientInput,
  CurrentUser,
  NewCaseInput,
  Problem,
  UpcomingHearing,
} from '../types';

interface StoredFile {
  bytes: Uint8Array;
  contentType: string;
}

/** A test account; every one uses MOCK_PASSWORD unless a test changes it. */
interface MockUser extends CurrentUser {
  password: string;
  isActive?: boolean;
  isLocked?: boolean;
}

/** An account as the administration API returns it (no password). */
function adminUser(user: MockUser): AdminUser {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    clientId: user.clientId,
    clientName: state.clients.find((c) => c.id === user.clientId)?.name ?? null,
    isActive: user.isActive ?? true,
    isLocked: user.isLocked ?? false,
    canSignIn: true,
    mustChangePassword: user.mustChangePassword,
    lastLoginAt: null,
    isSample: false,
  };
}

export const MOCK_PASSWORD = 'correct horse battery staple';
export const MOCK_ADMIN_EMAIL = 'admin@lexflow.test';
/** Who `renderApp` signs in by default: an Administrator (sees every case). */
export const DEFAULT_TEST_USER = MOCK_ADMIN_EMAIL;
/** The sample lead advocate of case-1005 (sees only the cases he leads or joins). */
export const ARYAN_EMAIL = 'aryan.goyal@lexflow.test';
/** A Paralegal on no case team until a test adds them (`mockAddMember`). */
export const MOCK_PARALEGAL_EMAIL = 'paralegal@lexflow.test';
// Like the server: only these roles may sign in at this stage.
const SIGN_IN_ROLES = new Set<string>(['Administrator', 'Advocate', 'Paralegal', 'Client']);

/** A case as the fake server stores it: without the per-user views (permissions, team). */
export type StoredCase = Omit<Case, 'permissions' | 'team'> & {
  members: { userId: string; role: 'associate' | 'paralegal' }[];
  /** Soft-deleted documents: off the case, kept until restored. */
  deletedDocuments: DeletedDocument[];
};

type Relation = Case['permissions']['relation'];
type Action =
  | 'view'
  | 'editDetails'
  | 'editListing'
  | 'changeStatus'
  | 'changeLead'
  | 'changeClient'
  | 'manageTeam'
  | 'archive'
  | 'manageHearings'
  | 'upload'
  | 'delete'
  | 'restore'
  | 'share';

// The same rules as the server (lexflow/authz.py).
const STAFF: Relation[] = ['admin', 'lead', 'associate', 'paralegal'];
const ADVOCATES: Relation[] = ['admin', 'lead', 'associate'];
const ALLOWED: Record<Action, Relation[]> = {
  view: STAFF,
  editDetails: ADVOCATES,
  editListing: STAFF,
  changeStatus: ADVOCATES,
  changeLead: ['admin'],
  changeClient: ['admin'],
  manageTeam: ['admin', 'lead'],
  archive: ['admin'],
  manageHearings: STAFF,
  upload: STAFF,
  delete: ['admin', 'lead'],
  restore: ['admin', 'lead'],
  share: ADVOCATES,
};
const allows = (rel: Relation, action: Action) => ALLOWED[action].includes(rel);
const FIELD_ACTIONS: [string, Action][] = [
  ['title', 'editDetails'],
  ['description', 'editDetails'],
  ['practiceArea', 'editDetails'],
  ['priority', 'editDetails'],
  ['courtName', 'editListing'],
  ['opposingParty', 'editListing'],
  ['status', 'changeStatus'],
  ['leadAdvocateId', 'changeLead'],
  ['clientId', 'changeClient'],
];

/** Like the server: on an archived case nothing may change except restoring it. */
export function permissionsFor(rel: Relation, isArchived = false): Case['permissions'] {
  const may = (action: Action) => allows(rel, action) && !isArchived;
  return {
    relation: rel,
    editableFields: FIELD_ACTIONS.filter(([, action]) => may(action)).map(([f]) => f),
    canChangeStatus: may('changeStatus'),
    canManageTeam: may('manageTeam'),
    canArchive: allows(rel, 'archive'),
    canManageHearings: may('manageHearings'),
    canUploadDocuments: may('upload'),
    canDeleteDocuments: may('delete'),
    canRestoreDocuments: may('restore'),
    canShareDocuments: may('share'),
  };
}

const FIELD_LABELS: Record<string, string> = {
  title: 'title',
  status: 'status',
  priority: 'priority',
  practiceArea: 'practice area',
  clientId: 'client',
  leadAdvocateId: 'lead advocate',
  courtName: 'court',
  opposingParty: 'opposing party',
  description: 'summary',
};
const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

interface State {
  clients: Client[];
  advocates: Advocate[];
  cases: StoredCase[];
  files: Map<string, StoredFile>;
  nextId: number;
  users: MockUser[];
  sessionUserId: string | null;
  /** Audit events the tests add (the fake API does not record its own). */
  audit: AuditEvent[];
  /** Extracted text by document id, set by tests (`mockSetText`). */
  texts: Map<string, { pageNumbers: boolean; sections: string[] }>;
}

const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-');

export const advocateId = (name: string) => `advocate-${slug(name)}`;

function nextHearing(c: Pick<Case, 'hearings'>, today: string): string | null {
  // Like the server: cancelled hearings never count.
  const dates = c.hearings
    .filter((h) => h.status === 'Scheduled')
    .map((h) => h.date)
    .sort();
  return dates.find((d) => d >= today) ?? dates.filter((d) => d < today).at(-1) ?? null;
}

function sortDocuments(documents: CaseDocument[]): CaseDocument[] {
  // Same rule as the server: newest first, same-day records by name.
  return [...documents].sort(
    (a, b) =>
      b.uploadedOn.localeCompare(a.uploadedOn) ||
      a.name.toLowerCase().localeCompare(b.name.toLowerCase()),
  );
}

function initialState(): State {
  const today = todayIsoDate();
  const advocates: Advocate[] = sampleAdvocates.map((a) => ({
    id: advocateId(a.name),
    name: a.name,
    email: a.email,
    isSample: true,
  }));
  const cases: StoredCase[] = mockCases.map((c) => {
    const detail: StoredCase = {
      members: [],
      deletedDocuments: [],
      id: c.id,
      caseNumber: c.caseNumber,
      title: c.title,
      status: c.status,
      priority: c.priority,
      practiceArea: c.practiceArea,
      clientId: c.clientId,
      clientName: c.clientName,
      leadAdvocateId: advocateId(c.leadAttorney),
      leadAttorney: c.leadAttorney,
      courtName: c.courtName ?? null,
      opposingParty: c.opposingParty ?? null,
      openedOn: c.openedOn,
      nextHearing: null,
      documentCount: c.documents.length,
      archivedAt: null,
      isSample: true,
      description: c.description,
      documents: sortDocuments(
        c.documents.map((d) => ({
          id: d.id,
          name: d.name,
          type: d.type,
          uploadedOn: d.uploadedOn,
          size: d.size,
          sizeBytes: null,
          hasFile: false,
          contentType: null,
          downloadUrl: null,
          uploadedBy: null,
          sharedWithClientAt: null,
          processing: null,
          isSample: true,
        })),
      ),
      hearings: c.hearings.map((h) => ({
        ...h,
        status: 'Scheduled' as const,
        cancellationReason: null,
        isSample: true,
      })),
      timeline: c.timeline.map((t) => ({
        ...t,
        actor: null,
        recordedAt: `${t.date}T09:00:00Z`,
        isSample: true,
      })),
    };
    detail.nextHearing = nextHearing(detail, today);
    return detail;
  });
  const users: MockUser[] = [
    {
      id: 'user-admin',
      name: 'Test Administrator',
      email: MOCK_ADMIN_EMAIL,
      role: 'Administrator',
      clientId: null,
      mustChangePassword: false,
      password: MOCK_PASSWORD,
    },
    ...advocates.map((a): MockUser => ({
      id: a.id,
      name: a.name,
      email: a.email,
      role: 'Advocate',
      clientId: null,
      mustChangePassword: false,
      password: MOCK_PASSWORD,
    })),
    {
      id: 'user-paralegal',
      name: 'Test Paralegal',
      email: MOCK_PARALEGAL_EMAIL,
      role: 'Paralegal',
      clientId: null,
      mustChangePassword: false,
      password: MOCK_PASSWORD,
    },
  ];
  return {
    clients: mockClients.map((c) => ({ ...c, company: c.company ?? null, isSample: true })),
    advocates,
    cases,
    files: new Map(),
    nextId: 1,
    users,
    sessionUserId: null,
    audit: [],
    texts: new Map(),
  };
}

const publicUser = ({ password: _password, ...user }: MockUser): CurrentUser => user;

function currentMockUser(): MockUser | undefined {
  return state.users.find((u) => u.id === state.sessionUserId);
}

function relationTo(c: StoredCase, user: MockUser | undefined): Relation {
  if (!user) return 'none';
  if (user.role === 'Administrator') return 'admin';
  if (user.role === 'Advocate' && c.leadAdvocateId === user.id) return 'lead';
  const member = c.members.find((m) => m.userId === user.id);
  if (member?.role === 'associate' && user.role === 'Advocate') return 'associate';
  if (member?.role === 'paralegal' && user.role === 'Paralegal') return 'paralegal';
  return 'none';
}

function caseOut({ members, deletedDocuments: _deleted, ...c }: StoredCase, rel: Relation): Case {
  const team = members
    .flatMap((m) => {
      const user = state.users.find((u) => u.id === m.userId);
      return user ? [{ id: user.id, name: user.name, role: user.role, memberRole: m.role }] : [];
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  return { ...c, team, permissions: permissionsFor(rel, c.archivedAt !== null) };
}

function currentActor(): { id: string; name: string } | null {
  const user = currentMockUser();
  return user ? { id: user.id, name: user.name } : null;
}

function visibleHearing(id: string) {
  for (const c of state.cases) {
    const hearing = c.hearings.find((h) => h.id === id);
    if (hearing) {
      const rel = relationTo(c, currentMockUser());
      return allows(rel, 'view') ? { c, rel, hearing } : null;
    }
  }
  return null;
}

const hearingNotFound = () => problem(404, 'hearing-not-found', 'No hearing with this id exists.');

function sortHearings<T extends { date: string; time: string | null }>(hearings: T[]): T[] {
  return [...hearings].sort(
    (a, b) => a.date.localeCompare(b.date) || (a.time ?? '99').localeCompare(b.time ?? '99'),
  );
}

const invalid = (errors: Problem['errors']) =>
  problem(422, 'validation-error', 'Correct the highlighted fields and try again.', errors);

/** The server's rules for a hearing's fields (only those present are checked). */
function hearingErrors(input: HearingChanges, checkDate: boolean): NonNullable<Problem['errors']> {
  const errors: NonNullable<Problem['errors']> = [];
  if (checkDate && input.date !== undefined && (input.date ?? '') < todayIsoDate()) {
    errors.push({ field: 'date', message: 'The hearing date cannot be in the past.' });
  }
  const time = input.time?.trim();
  if (time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) {
    errors.push({
      field: 'time',
      message: 'Enter the time as HH:MM (24-hour), or leave it blank.',
    });
  }
  if (input.court !== undefined && !(input.court ?? '').trim()) {
    errors.push({ field: 'court', message: 'Enter the court or forum.' });
  }
  if (input.purpose !== undefined && !(input.purpose ?? '').trim()) {
    errors.push({ field: 'purpose', message: 'Enter the purpose of the hearing.' });
  }
  return errors;
}

/** The server's rules for a client's details (only those present are checked). */
function clientErrors(input: ClientChanges): NonNullable<Problem['errors']> {
  const errors: NonNullable<Problem['errors']> = [];
  if (input.name !== undefined && (input.name ?? '').trim().length < 2) {
    errors.push({ field: 'name', message: "Enter the client's name (at least 2 characters)." });
  }
  if (input.email !== undefined && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((input.email ?? '').trim())) {
    errors.push({ field: 'email', message: 'Enter an e-mail address such as name@example.com.' });
  }
  if (input.phone !== undefined && !/^\+?[0-9 ()-]{7,20}$/.test((input.phone ?? '').trim())) {
    errors.push({
      field: 'phone',
      message: 'Enter a phone number: digits, spaces, +, - or brackets (7 to 20).',
    });
  }
  return errors;
}

/** A case as its client sees it in the portal (no internal details). */
function portalSummary(c: StoredCase) {
  return {
    id: c.id,
    caseNumber: c.caseNumber,
    title: c.title,
    status: c.status,
    practiceArea: c.practiceArea,
    leadAttorney: c.leadAttorney,
    courtName: c.courtName,
    openedOn: c.openedOn,
    nextHearing: c.nextHearing,
  };
}

const EXTRACTABLE = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]);

/** What the server reports right after an upload (its reasons, word for word). */
function initialProcessing(contentType: string): DocumentProcessing {
  const base = {
    reasonCode: null,
    reason: null,
    pageCount: null,
    sectionCount: null,
    chunkCount: null,
    indexStatus: 'disabled' as const,
    updatedAt: new Date().toISOString(),
  };
  if (EXTRACTABLE.has(contentType)) return { ...base, status: 'queued' };
  return {
    ...base,
    status: 'unsupported',
    reasonCode: 'unsupported-type',
    reason: contentType.startsWith('image/')
      ? 'Text is not extracted from images (OCR is not available).'
      : 'Text is not extracted from old Word (.doc) files. Save it as .docx and upload it again to make its text available.',
  };
}

/** Move a document's processing on, as the worker would (tests only). */
/**
 * Give a document extracted text, as the worker would: one string per PDF
 * page (``pages``) or per part of a document without pages (tests only).
 */
export function mockSetText(
  documentId: string,
  sections: string[],
  { pages = true }: { pages?: boolean } = {},
): void {
  state.texts.set(documentId, { pageNumbers: pages, sections });
  mockSetProcessing(documentId, {
    status: 'ready',
    pageCount: pages ? sections.length : null,
    sectionCount: sections.length,
    chunkCount: sections.length,
  });
}

export function mockSetProcessing(documentId: string, change: Partial<DocumentProcessing>): void {
  for (const c of state.cases) {
    const doc = c.documents.find((d) => d.id === documentId);
    if (doc?.processing) {
      doc.processing = { ...doc.processing, ...change, updatedAt: new Date().toISOString() };
      return;
    }
  }
  throw new Error(`no processed document ${documentId}`);
}

/** As for a file stored before text extraction existed: no job at all. */
export function mockClearProcessing(documentId: string): void {
  for (const c of state.cases) {
    const doc = c.documents.find((d) => d.id === documentId);
    if (doc) {
      doc.processing = null;
      return;
    }
  }
  throw new Error(`no document ${documentId}`);
}

const caseArchived = () =>
  problem(409, 'case-archived', 'This case is archived. Restore it before making changes.');

function addTimeline(c: StoredCase, label: string, description: string): void {
  const user = currentMockUser();
  c.timeline.push({
    id: `${c.id}-t${state.nextId++}`,
    date: todayIsoDate(),
    label,
    description,
    actor: user ? { id: user.id, name: user.name } : null,
    recordedAt: new Date().toISOString(),
    isSample: false,
  });
}

/** The case and the signed-in user's relation to it, if they may see it. */
function visibleCase(id: string): { c: StoredCase; rel: Relation } | null {
  const c = state.cases.find((x) => x.id === id);
  if (!c) return null;
  const rel = relationTo(c, currentMockUser());
  return allows(rel, 'view') ? { c, rel } : null;
}

const caseNotFound = () => problem(404, 'case-not-found', 'No case with this id exists.');
const forbidden = () => problem(403, 'forbidden', 'You do not have permission to do this.');

/** Sign a test account in, as if it had used the sign-in form. */
export function mockSignIn(email: string): void {
  const user = state.users.find((u) => u.email === email);
  if (!user) throw new Error(`no mock user ${email}`);
  state.sessionUserId = user.id;
}

/** The signed-in test account as `GET /api/auth/me` returns it, or null. */
export function mockCurrentUser(): CurrentUser | null {
  const user = currentMockUser();
  return user ? publicUser(user) : null;
}

/** Put a test account on a case team. */
export function mockAddMember(
  caseId: string,
  email: string,
  role: 'associate' | 'paralegal',
): void {
  const c = state.cases.find((x) => x.id === caseId);
  const user = state.users.find((u) => u.email === email);
  if (!c || !user) throw new Error(`no case ${caseId} or user ${email}`);
  c.members.push({ userId: user.id, role });
}

/** End the session on the "server" (as when it expires or is revoked). */
export function mockSignOut(): void {
  state.sessionUserId = null;
}

/** Add a test account (e.g. one that must change its temporary password). */
export function mockAddUser(
  user: Partial<MockUser> & { email: string; role: MockUser['role'] },
): MockUser {
  const created: MockUser = {
    id: `user-${state.nextId++}`,
    name: user.email,
    clientId: null,
    mustChangePassword: false,
    password: MOCK_PASSWORD,
    ...user,
  };
  state.users.push(created);
  return created;
}

let state: State = initialState();

/** Called before each test (see setup.ts). */
export function resetMockApi(): void {
  state = initialState();
}

/** Read the fake server's current data in a test. */
export function mockApiState(): Readonly<State> {
  return state;
}

/** A fresh copy of an API-shaped sample case, e.g. `sampleApiCase('case-1005')`. */
export function sampleApiCase(id: string): Case {
  const found = initialState().cases.find((c) => c.id === id);
  if (!found) throw new Error(`no sample case ${id}`);
  return caseOut(found, 'admin');
}

export function problem(
  status: number,
  code: string,
  detail: string,
  errors: Problem['errors'] = [],
): HttpResponse<Problem> {
  return HttpResponse.json(
    {
      type: `https://lexflow.invalid/problems/${code}`,
      title: 'Error',
      status,
      code,
      detail,
      errors,
    },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

function summary(c: StoredCase): CaseSummary {
  return {
    id: c.id,
    caseNumber: c.caseNumber,
    title: c.title,
    status: c.status,
    priority: c.priority,
    practiceArea: c.practiceArea,
    clientId: c.clientId,
    clientName: c.clientName,
    leadAdvocateId: c.leadAdvocateId,
    leadAttorney: c.leadAttorney,
    courtName: c.courtName,
    opposingParty: c.opposingParty,
    openedOn: c.openedOn,
    nextHearing: c.nextHearing,
    documentCount: c.documents.length,
    archivedAt: c.archivedAt,
    isSample: c.isSample,
  };
}

const KINDS: Record<string, { type: string; contentType: string; magic?: string }> = {
  pdf: { type: 'PDF', contentType: 'application/pdf', magic: '%PDF-' },
  doc: { type: 'Word document', contentType: 'application/msword' },
  docx: {
    type: 'Word document',
    contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  },
  txt: { type: 'Text', contentType: 'text/plain' },
  png: { type: 'Image', contentType: 'image/png' },
  jpg: { type: 'Image', contentType: 'image/jpeg' },
  jpeg: { type: 'Image', contentType: 'image/jpeg' },
  gif: { type: 'Image', contentType: 'image/gif' },
  webp: { type: 'Image', contentType: 'image/webp' },
};

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export const handlers = [
  // Like the server: every change must carry the app's CSRF header. Falls
  // through (returns nothing) to the real handlers when it does.
  http.all('*/api/*', ({ request }) => {
    if (UNSAFE.has(request.method) && request.headers.get('X-LexFlow-Request') !== '1') {
      return problem(
        403,
        'csrf-header-missing',
        'This request did not come from the LexFlow app and was refused.',
      );
    }
    return undefined;
  }),

  // Like the server's session gate and require_user dependency.
  http.all('*/api/*', ({ request }) => {
    const { pathname } = new URL(request.url);
    const isPublic =
      (request.method === 'GET' && pathname === '/api/health') ||
      (request.method === 'POST' &&
        (pathname === '/api/auth/login' || pathname === '/api/auth/logout'));
    if (isPublic) return undefined;
    const user = currentMockUser();
    if (!user) return problem(401, 'not-authenticated', 'Sign in to continue.');
    const passwordRoutes = pathname === '/api/auth/me' || pathname === '/api/auth/password';
    if (user.mustChangePassword && !passwordRoutes) {
      return problem(403, 'password-change-required', 'Choose a new password before continuing.');
    }
    // Like the server: Client accounts reach only the portal, staff never do.
    const portal = pathname.startsWith('/api/portal/');
    if (!passwordRoutes && portal !== (user.role === 'Client')) return forbidden();
    return undefined;
  }),

  http.get('*/api/auth/me', () => {
    const user = currentMockUser();
    return user ? HttpResponse.json(publicUser(user)) : problem(401, 'not-authenticated', '');
  }),

  http.post('*/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    const user = state.users.find(
      (u) => (u.email ?? '').toLowerCase() === body.email.trim().toLowerCase(),
    );
    if (
      !user ||
      user.password !== body.password ||
      !SIGN_IN_ROLES.has(user.role) ||
      user.isActive === false ||
      user.isLocked
    ) {
      return problem(401, 'invalid-credentials', 'Email or password is incorrect.');
    }
    state.sessionUserId = user.id;
    return HttpResponse.json(publicUser(user));
  }),

  http.post('*/api/auth/logout', () => {
    state.sessionUserId = null;
    return new HttpResponse(null, { status: 204 });
  }),

  http.post('*/api/auth/password', async ({ request }) => {
    const user = currentMockUser();
    if (!user) return problem(401, 'not-authenticated', 'Sign in to continue.');
    const body = (await request.json()) as { currentPassword: string; newPassword: string };
    const invalid = (field: string, message: string) =>
      problem(422, 'validation-error', 'Correct the highlighted fields and try again.', [
        { field, message },
      ]);
    if (body.currentPassword !== user.password) {
      return invalid('currentPassword', 'Your current password is incorrect.');
    }
    if (body.newPassword.length < 12) return invalid('newPassword', 'Use at least 12 characters.');
    user.password = body.newPassword;
    user.mustChangePassword = false;
    return HttpResponse.json(publicUser(user));
  }),

  http.get('*/api/cases', ({ request }) => {
    const archived = new URL(request.url).searchParams.get('archived') ?? 'exclude';
    const wanted = (c: StoredCase) =>
      archived === 'include' || (archived === 'only') === (c.archivedAt !== null);
    return HttpResponse.json(
      state.cases
        .filter((c) => allows(relationTo(c, currentMockUser()), 'view') && wanted(c))
        .sort((a, b) => b.openedOn.localeCompare(a.openedOn))
        .map(summary),
    );
  }),

  http.patch('*/api/cases/:id', async ({ params, request }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    const { c, rel } = found;
    const changes = (await request.json()) as CaseChanges;
    const fields = Object.keys(changes);
    const notPermitted = fields.filter(
      (f) => !FIELD_ACTIONS.some(([name, action]) => name === f && allows(rel, action)),
    );
    if (notPermitted.length > 0) {
      const message = 'You cannot change this field on this case.';
      return problem(
        403,
        'field-not-permitted',
        message,
        notPermitted.map((field) => ({ field, message })),
      );
    }
    if (fields.length > 0 && c.archivedAt !== null) return caseArchived();
    const errors: Problem['errors'] = [];
    if (changes.title !== undefined && (changes.title ?? '').trim().length < 4) {
      errors.push({
        field: 'title',
        message: 'Enter a descriptive case title (at least 4 characters).',
      });
    }
    if (changes.description !== undefined && (changes.description ?? '').trim().length < 10) {
      errors.push({
        field: 'description',
        message: 'Provide a short summary (at least 10 characters).',
      });
    }
    if (errors.length > 0) {
      return problem(
        422,
        'validation-error',
        'Correct the highlighted fields and try again.',
        errors,
      );
    }
    const record = c as unknown as Record<string, unknown>;
    const described: string[] = [];
    for (const field of fields) {
      let value = (changes as Record<string, unknown>)[field];
      if (typeof value === 'string') value = value.trim();
      if ((field === 'courtName' || field === 'opposingParty') && value === '') value = null;
      if (record[field] === value) continue;
      const label = capitalise(FIELD_LABELS[field]);
      described.push(
        field === 'status' || field === 'priority'
          ? `${label} changed from ${String(record[field])} to ${String(value)}.`
          : `${label} updated.`,
      );
      record[field] = value;
      if (field === 'leadAdvocateId') {
        c.leadAttorney = state.users.find((u) => u.id === value)?.name ?? c.leadAttorney;
        c.members = c.members.filter((m) => m.userId !== value);
      }
      if (field === 'clientId') {
        c.clientName = state.clients.find((x) => x.id === value)?.name ?? c.clientName;
      }
    }
    if (described.length > 0) addTimeline(c, 'Case details updated', described.join(' '));
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.post('*/api/cases/:id/:change', ({ params }) => {
    const change = String(params.change);
    if (change !== 'archive' && change !== 'unarchive') return undefined;
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    const { c, rel } = found;
    if (!allows(rel, 'archive')) return forbidden();
    const archive = change === 'archive';
    if ((c.archivedAt !== null) !== archive) {
      c.archivedAt = archive ? new Date().toISOString() : null;
      addTimeline(
        c,
        archive ? 'Case archived' : 'Case restored',
        archive
          ? 'Archived: kept in full, read-only and hidden from the case list.'
          : 'Restored from the archive.',
      );
    }
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.post('*/api/cases/:id/team', async ({ params, request }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    const { c, rel } = found;
    if (!allows(rel, 'manageTeam')) return forbidden();
    if (c.archivedAt !== null) return caseArchived();
    const { userId } = (await request.json()) as { userId: string };
    const member = state.users.find((u) => u.id === userId);
    const invalid = (message: string) =>
      problem(422, 'validation-error', 'Correct the highlighted fields and try again.', [
        { field: 'userId', message },
      ]);
    if (!member || (member.role !== 'Advocate' && member.role !== 'Paralegal')) {
      return invalid('Choose an active advocate or paralegal.');
    }
    if (member.id === c.leadAdvocateId) {
      return invalid('The lead advocate already leads this case.');
    }
    if (!c.members.some((m) => m.userId === member.id)) {
      const role = member.role === 'Advocate' ? 'associate' : 'paralegal';
      c.members.push({ userId: member.id, role });
      const as = role === 'associate' ? 'an associate advocate' : 'a paralegal';
      addTimeline(c, 'Case team updated', `${member.name} joined the case team as ${as}.`);
    }
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.delete('*/api/cases/:id/team/:userId', ({ params }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    const { c, rel } = found;
    if (!allows(rel, 'manageTeam')) return forbidden();
    if (c.archivedAt !== null) return caseArchived();
    const userId = String(params.userId);
    if (!c.members.some((m) => m.userId === userId)) {
      return problem(404, 'member-not-found', 'That person is not on this case team.');
    }
    c.members = c.members.filter((m) => m.userId !== userId);
    const name = state.users.find((u) => u.id === userId)?.name ?? 'A member';
    addTimeline(c, 'Case team updated', `${name} left the case team.`);
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.post('*/api/cases/:id/hearings', async ({ params, request }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    const { c, rel } = found;
    if (!allows(rel, 'manageHearings')) return forbidden();
    if (c.archivedAt !== null) return caseArchived();
    const input = (await request.json()) as HearingInput;
    const errors = hearingErrors(input, true);
    if (errors.length > 0) return invalid(errors);
    const hearing = {
      id: `${c.id}-h${state.nextId++}`,
      date: input.date,
      time: input.time?.trim() || null,
      court: input.court.trim(),
      purpose: input.purpose.trim(),
      status: 'Scheduled' as const,
      cancellationReason: null,
      isSample: false,
    };
    c.hearings = sortHearings([...c.hearings, hearing]);
    c.nextHearing = nextHearing(c, todayIsoDate());
    addTimeline(c, 'Hearing scheduled', `${hearing.purpose}, ${hearing.court}.`);
    return HttpResponse.json(caseOut(c, rel), { status: 201 });
  }),

  http.patch('*/api/hearings/:id', async ({ params, request }) => {
    const found = visibleHearing(String(params.id));
    if (!found) return hearingNotFound();
    const { c, rel, hearing } = found;
    if (!allows(rel, 'manageHearings')) return forbidden();
    if (c.archivedAt !== null) return caseArchived();
    if (hearing.status === 'Cancelled') {
      return problem(
        409,
        'hearing-cancelled',
        'This hearing was cancelled and cannot be changed. Schedule a new one instead.',
      );
    }
    const changes = (await request.json()) as HearingChanges;
    const errors = hearingErrors(changes, changes.date !== undefined);
    if (errors.length > 0) return invalid(errors);
    const before = JSON.stringify(hearing);
    if (changes.date) hearing.date = changes.date;
    if (changes.time !== undefined) hearing.time = changes.time?.trim() || null;
    if (changes.court) hearing.court = changes.court.trim();
    if (changes.purpose) hearing.purpose = changes.purpose.trim();
    if (JSON.stringify(hearing) !== before) {
      c.hearings = sortHearings(c.hearings);
      c.nextHearing = nextHearing(c, todayIsoDate());
      addTimeline(c, 'Hearing updated', `${hearing.purpose}: details updated.`);
    }
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.post('*/api/hearings/:id/cancel', async ({ params, request }) => {
    const found = visibleHearing(String(params.id));
    if (!found) return hearingNotFound();
    const { c, rel, hearing } = found;
    if (!allows(rel, 'manageHearings')) return forbidden();
    if (c.archivedAt !== null) return caseArchived();
    const { reason } = (await request.json()) as { reason: string | null };
    if (hearing.status !== 'Cancelled') {
      hearing.status = 'Cancelled';
      hearing.cancellationReason = reason?.trim() || null;
      c.nextHearing = nextHearing(c, todayIsoDate());
      const because = hearing.cancellationReason ? ` Reason: ${hearing.cancellationReason}` : '';
      addTimeline(c, 'Hearing cancelled', `${hearing.purpose} was cancelled.${because}`);
    }
    return HttpResponse.json(caseOut(c, rel));
  }),

  http.all('*/api/admin/*', () => {
    // Like the server: Administrators only.
    return currentMockUser()?.role === 'Administrator' ? undefined : forbidden();
  }),

  http.get('*/api/admin/audit', ({ request }) => {
    const params = new URL(request.url).searchParams;
    const action = params.get('action') ?? '';
    const outcome = params.get('outcome') ?? '';
    const limit = Number(params.get('limit') ?? 50);
    const before = params.get('before');
    let events = [...state.audit].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
    if (action) {
      events = events.filter((e) =>
        action.endsWith('.') ? e.action.startsWith(action) : e.action === action,
      );
    }
    if (outcome) events = events.filter((e) => e.outcome === outcome);
    if (before) events = events.slice(events.findIndex((e) => e.id === before) + 1);
    const pageOf = events.slice(0, limit);
    return HttpResponse.json({
      events: pageOf,
      nextBefore: events.length > limit ? (pageOf.at(-1)?.id ?? null) : null,
    });
  }),

  http.get('*/api/admin/users', () =>
    HttpResponse.json(
      [...state.users]
        .sort((a, b) => a.role.localeCompare(b.role) || a.name.localeCompare(b.name))
        .map(adminUser),
    ),
  ),

  http.post('*/api/admin/users', async ({ request }) => {
    const input = (await request.json()) as AdminUserInput;
    const errors: NonNullable<Problem['errors']> = [];
    if (
      state.users.some((u) => (u.email ?? '').toLowerCase() === input.email.trim().toLowerCase())
    ) {
      errors.push({
        field: 'email',
        message: 'An account with this e-mail address already exists.',
      });
    }
    if (input.role === 'Client' && !input.clientId) {
      errors.push({ field: 'clientId', message: 'Choose the client this account represents.' });
    }
    if (input.temporaryPassword.length < 12) {
      errors.push({ field: 'temporaryPassword', message: 'Use at least 12 characters.' });
    }
    if (errors.length > 0) return invalid(errors);
    const created = mockAddUser({
      email: input.email.trim(),
      name: input.name.trim(),
      role: input.role,
      clientId: input.role === 'Client' ? (input.clientId ?? null) : null,
      password: input.temporaryPassword,
      mustChangePassword: true,
    });
    return HttpResponse.json(adminUser(created), { status: 201 });
  }),

  http.patch('*/api/admin/users/:id', async ({ params, request }) => {
    const user = state.users.find((u) => u.id === params.id);
    if (!user) return problem(404, 'user-not-found', 'No account with this id exists.');
    const changes = (await request.json()) as AdminUserChanges;
    if (changes.name) user.name = changes.name.trim();
    if (changes.email) user.email = changes.email.trim();
    return HttpResponse.json(adminUser(user));
  }),

  http.post('*/api/admin/users/:id/:action', async ({ params, request }) => {
    const user = state.users.find((u) => u.id === params.id);
    if (!user) return problem(404, 'user-not-found', 'No account with this id exists.');
    const me = currentMockUser();
    const action = String(params.action);
    if (action === 'disable') {
      if (user.id === me?.id)
        return problem(409, 'conflict', 'You cannot disable your own account.');
      user.isActive = false;
    } else if (action === 'enable') {
      user.isActive = true;
    } else if (action === 'unlock') {
      user.isLocked = false;
    } else if (action === 'password') {
      if (user.id === me?.id) {
        return problem(409, 'conflict', 'Change your own password from your account page instead.');
      }
      const { temporaryPassword } = (await request.json()) as { temporaryPassword: string };
      if (temporaryPassword.length < 12) {
        return invalid([{ field: 'temporaryPassword', message: 'Use at least 12 characters.' }]);
      }
      user.password = temporaryPassword;
      user.mustChangePassword = true;
      user.isLocked = false;
    } else {
      return undefined;
    }
    return HttpResponse.json(adminUser(user));
  }),

  http.get('*/api/staff', () =>
    HttpResponse.json(
      state.users
        .filter((u) => u.role === 'Advocate' || u.role === 'Paralegal')
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(({ id, name, role }) => ({ id, name, role })),
    ),
  ),

  http.get('*/api/cases/:id', ({ params }) => {
    const found = visibleCase(String(params.id));
    return found ? HttpResponse.json(caseOut(found.c, found.rel)) : caseNotFound();
  }),

  http.post('*/api/cases', async ({ request }) => {
    const user = currentMockUser();
    if (!user || (user.role !== 'Administrator' && user.role !== 'Advocate')) return forbidden();
    const input = (await request.json()) as NewCaseInput;
    if (user.role !== 'Administrator' && input.leadAdvocateId !== user.id) {
      const message = 'You can only open cases with yourself as the lead advocate.';
      return problem(403, 'field-not-permitted', message, [{ field: 'leadAdvocateId', message }]);
    }
    const today = todayIsoDate();
    const errors: Problem['errors'] = [];
    if (input.title.trim().length < 4) {
      errors.push({
        field: 'title',
        message: 'Enter a descriptive case title (at least 4 characters).',
      });
    }
    if (input.description.trim().length < 10) {
      errors.push({
        field: 'description',
        message: 'Provide a short summary (at least 10 characters).',
      });
    }
    const client = state.clients.find((c) => c.id === input.clientId);
    if (!client) errors.push({ field: 'clientId', message: 'Select a client from the list.' });
    const advocate = state.advocates.find((a) => a.id === input.leadAdvocateId);
    if (!advocate)
      errors.push({ field: 'leadAdvocateId', message: 'Select a lead advocate from the list.' });
    if (input.nextHearing && input.nextHearing < today) {
      errors.push({
        field: 'nextHearing',
        message: 'The next hearing date cannot be in the past.',
      });
    }
    if (errors.length > 0 || !client || !advocate) {
      return problem(
        422,
        'validation-error',
        'Correct the highlighted fields and try again.',
        errors,
      );
    }

    const year = today.slice(0, 4);
    const highest = Math.max(
      0,
      ...state.cases
        .filter((c) => c.caseNumber.startsWith(`LF-${year}-`))
        .map((c) => Number(c.caseNumber.slice(8))),
    );
    const id = `case-new-${state.nextId++}`;
    const created: StoredCase = {
      members: [],
      deletedDocuments: [],
      id,
      caseNumber: `LF-${year}-${String(highest + 1).padStart(4, '0')}`,
      title: input.title.trim(),
      status: input.status,
      priority: input.priority,
      practiceArea: input.practiceArea,
      clientId: client.id,
      clientName: client.name,
      leadAdvocateId: advocate.id,
      leadAttorney: advocate.name,
      courtName: input.courtName?.trim() || null,
      opposingParty: input.opposingParty?.trim() || null,
      openedOn: today,
      nextHearing: input.nextHearing ?? null,
      documentCount: 0,
      archivedAt: null,
      isSample: false,
      description: input.description.trim(),
      documents: [],
      hearings: input.nextHearing
        ? [
            {
              id: `${id}-h1`,
              date: input.nextHearing,
              time: null,
              court: 'To be notified',
              purpose: 'First listing',
              status: 'Scheduled' as const,
              cancellationReason: null,
              isSample: false,
            },
          ]
        : [],
      timeline: [
        {
          id: `${id}-t1`,
          date: today,
          label: 'Matter opened',
          description: 'Matter created in LexFlow.',
          actor: { id: user.id, name: user.name },
          recordedAt: new Date().toISOString(),
          isSample: false,
        },
      ],
    };
    state.cases.push(created);
    return HttpResponse.json(caseOut(created, relationTo(created, user)), { status: 201 });
  }),

  http.get('*/api/clients/options', () => {
    const user = currentMockUser();
    if (user?.role !== 'Administrator' && user?.role !== 'Advocate') return forbidden();
    return HttpResponse.json(
      [...state.clients]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(({ id, name, isSample }) => ({ id, name, isSample })),
    );
  }),

  http.get('*/api/clients/:id', ({ params }) => {
    const user = currentMockUser();
    const client = state.clients.find((c) => c.id === params.id);
    const cases = state.cases.filter(
      (c) => c.clientId === params.id && allows(relationTo(c, user), 'view'),
    );
    if (!client || (user?.role !== 'Administrator' && cases.length === 0)) {
      return problem(404, 'client-not-found', 'No client with this id exists.');
    }
    const canEdit =
      user?.role === 'Administrator' ||
      cases.some((c) => ['lead', 'associate'].includes(relationTo(c, user)));
    return HttpResponse.json({ ...client, cases: cases.map(summary), canEdit });
  }),

  http.post('*/api/clients', async ({ request }) => {
    const user = currentMockUser();
    if (user?.role !== 'Administrator' && user?.role !== 'Advocate') return forbidden();
    const input = (await request.json()) as ClientInput;
    const errors = clientErrors(input);
    if (errors.length > 0) return invalid(errors);
    const client: Client = {
      id: `client-new-${state.nextId++}`,
      name: input.name.trim(),
      email: input.email.trim(),
      phone: input.phone.trim(),
      company: input.company?.trim() || null,
      isSample: false,
    };
    state.clients.push(client);
    return HttpResponse.json(client, { status: 201 });
  }),

  http.patch('*/api/clients/:id', async ({ params, request }) => {
    const user = currentMockUser();
    const client = state.clients.find((c) => c.id === params.id);
    const cases = state.cases.filter(
      (c) => c.clientId === params.id && allows(relationTo(c, user), 'view'),
    );
    if (!client || (user?.role !== 'Administrator' && cases.length === 0)) {
      return problem(404, 'client-not-found', 'No client with this id exists.');
    }
    const canEdit =
      user?.role === 'Administrator' ||
      cases.some((c) => ['lead', 'associate'].includes(relationTo(c, user)));
    if (!canEdit) return forbidden();
    const changes = (await request.json()) as ClientChanges;
    const errors = clientErrors(changes);
    if (errors.length > 0) return invalid(errors);
    if (changes.name) client.name = changes.name.trim();
    if (changes.email) client.email = changes.email.trim();
    if (changes.phone) client.phone = changes.phone.trim();
    if (changes.company !== undefined) client.company = changes.company?.trim() || null;
    for (const c of state.cases) if (c.clientId === client.id) c.clientName = client.name;
    return HttpResponse.json(client);
  }),

  http.get('*/api/clients', () => {
    const user = currentMockUser();
    const visibleClientIds = new Set(
      state.cases.filter((c) => allows(relationTo(c, user), 'view')).map((c) => c.clientId),
    );
    return HttpResponse.json(
      [...state.clients]
        .filter((c) => user?.role === 'Administrator' || visibleClientIds.has(c.id))
        .sort((a, b) => a.name.localeCompare(b.name)),
    );
  }),

  http.get('*/api/advocates', () =>
    HttpResponse.json([...state.advocates].sort((a, b) => a.name.localeCompare(b.name))),
  ),

  http.get('*/api/hearings', ({ request }) => {
    const params = new URL(request.url).searchParams;
    const from = params.get('from') ?? todayIsoDate();
    const to = params.get('to') ?? from;
    if (to < from) {
      return invalid([
        { field: 'to', message: 'The end date must be on or after the start date.' },
      ]);
    }
    const includeCancelled = params.get('includeCancelled') === 'true';
    const limit = Number(params.get('limit') ?? 200);
    const user = currentMockUser();
    const all = state.cases
      .filter((c) => allows(relationTo(c, user), 'view') && c.archivedAt === null)
      .flatMap((c) =>
        c.hearings.map((h) => ({
          ...h,
          caseId: c.id,
          caseTitle: c.title,
          caseNumber: c.caseNumber,
          leadAttorney: c.leadAttorney,
        })),
      )
      .filter(
        (h) => h.date >= from && h.date <= to && (includeCancelled || h.status === 'Scheduled'),
      )
      .sort(
        (a, b) => a.date.localeCompare(b.date) || (a.time ?? '99').localeCompare(b.time ?? '99'),
      );
    return HttpResponse.json({ hearings: all.slice(0, limit), truncated: all.length > limit });
  }),

  http.get('*/api/hearings/upcoming', ({ request }) => {
    const limit = Number(new URL(request.url).searchParams.get('limit') ?? 5);
    const today = todayIsoDate();
    const upcoming: UpcomingHearing[] = state.cases
      .filter((c) => allows(relationTo(c, currentMockUser()), 'view') && c.archivedAt === null)
      .flatMap((c) =>
        c.hearings
          .filter((h) => h.status === 'Scheduled')
          .map((h) => ({
            ...h,
            caseId: c.id,
            caseTitle: c.title,
            caseNumber: c.caseNumber,
          })),
      )
      .filter((h) => h.date >= today)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(0, limit);
    return HttpResponse.json(upcoming);
  }),

  http.post('*/api/cases/:id/documents', async ({ params, request }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    if (!allows(found.rel, 'upload')) return forbidden();
    const c = found.c;
    if (c.archivedAt !== null) return caseArchived();
    const file = (await request.formData()).get('file');
    if (!(file instanceof Blob)) {
      return problem(422, 'validation-error', 'Correct the highlighted fields and try again.', [
        { field: 'file', message: 'Field required' },
      ]);
    }
    const name = (file as File).name;
    const kind = KINDS[name.split('.').pop()?.toLowerCase() ?? ''];
    if (!kind) {
      return problem(
        415,
        'unsupported-type',
        `${name} is not a supported file type. Use ${ACCEPTED_TYPES_LABEL}.`,
      );
    }
    if (c.documents.some((d) => d.name.toLowerCase() === name.toLowerCase())) {
      return problem(409, 'duplicate', `${name} is already attached to this case.`);
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.length === 0) return problem(422, 'empty', `${name} is empty.`);
    if (
      kind.magic &&
      !new TextDecoder().decode(bytes.slice(0, kind.magic.length)).startsWith(kind.magic)
    ) {
      return problem(415, 'content-mismatch', `The contents of ${name} don't match its file type.`);
    }
    const id = `doc-new-${state.nextId++}`;
    const document: CaseDocument = {
      id,
      name,
      type: kind.type,
      uploadedOn: todayIsoDate(),
      size: formatFileSize(bytes.length),
      sizeBytes: bytes.length,
      hasFile: true,
      contentType: kind.contentType,
      downloadUrl: `/api/documents/${id}/download`,
      uploadedBy: currentActor(),
      sharedWithClientAt: null,
      processing: initialProcessing(kind.contentType),
      isSample: false,
    };
    state.files.set(id, { bytes, contentType: kind.contentType });
    c.documents = sortDocuments([document, ...c.documents]);
    c.documentCount = c.documents.length;
    return HttpResponse.json(document, { status: 201 });
  }),

  http.delete('*/api/documents/:id', ({ params }) => {
    const id = String(params.id);
    const owner = state.cases.find((c) => c.documents.some((d) => d.id === id));
    const rel = owner ? relationTo(owner, currentMockUser()) : 'none';
    if (!owner || !allows(rel, 'view')) {
      return problem(404, 'document-not-found', 'No document with this id exists.');
    }
    if (!allows(rel, 'delete')) return forbidden();
    if (owner.archivedAt !== null) return caseArchived();
    // Soft: off the case, file kept, restorable.
    const document = owner.documents.find((d) => d.id === id);
    owner.documents = owner.documents.filter((d) => d.id !== id);
    owner.documentCount = owner.documents.length;
    if (document) {
      owner.deletedDocuments.unshift({
        ...document,
        sharedWithClientAt: null, // deleting stops sharing
        deletedAt: new Date().toISOString(),
        deletedBy: currentActor(),
      });
    }
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('*/api/documents/:id/text', ({ params, request }) => {
    const id = String(params.id);
    const owner = state.cases.find((c) => c.documents.some((d) => d.id === id));
    const rel = owner ? relationTo(owner, currentMockUser()) : 'none';
    if (!owner || !allows(rel, 'view')) {
      return problem(404, 'document-not-found', 'No document with this id exists.');
    }
    const doc = owner.documents.find((d) => d.id === id);
    const text = state.texts.get(id);
    if (!doc?.processing || doc.processing.status !== 'ready' || !text) {
      const reason = !doc?.processing
        ? 'This record has no stored file, so it has no text.'
        : doc.processing.status === 'failed'
          ? `Text extraction failed: ${doc.processing.reason}`
          : (doc.processing.reason ??
            'The text has not been extracted yet. It is waiting to be processed.');
      return problem(409, 'text-not-available', reason);
    }
    const number = Number(new URL(request.url).searchParams.get('section') ?? 1);
    if (number < 1 || number > text.sections.length) {
      return problem(404, 'section-not-found', `This document has ${text.sections.length} parts.`);
    }
    return HttpResponse.json({
      documentId: id,
      documentName: doc.name,
      extractor: 'pypdf 6.21.1',
      pageCount: text.pageNumbers ? text.sections.length : null,
      sectionCount: text.sections.length,
      charCount: text.sections.join('').length,
      extractedAt: '2026-10-20T09:00:00Z',
      section: {
        number,
        pageNumber: text.pageNumbers ? number : null,
        text: text.sections[number - 1],
        chunkCount: 1,
      },
    });
  }),

  http.post('*/api/documents/:id/reprocess', ({ params }) => {
    const id = String(params.id);
    const owner = state.cases.find((c) => c.documents.some((d) => d.id === id));
    const rel = owner ? relationTo(owner, currentMockUser()) : 'none';
    if (!owner || !allows(rel, 'view')) {
      return problem(404, 'document-not-found', 'No document with this id exists.');
    }
    if (!allows(rel, 'upload')) return forbidden();
    if (owner.archivedAt !== null) return caseArchived();
    const doc = owner.documents.find((d) => d.id === id);
    if (!doc?.hasFile) {
      return problem(422, 'no-file', 'This record has no stored file, so it has no text.');
    }
    const status = doc.processing?.status;
    if (status === 'queued' || status === 'processing') {
      return problem(409, 'already-processing', 'The text is already waiting to be extracted.');
    }
    if (status === 'unsupported') {
      return problem(409, 'unsupported', doc.processing?.reason ?? 'Not extracted.');
    }
    // A stored file never queued (uploaded before extraction existed) gets a new job.
    doc.processing = {
      ...(doc.processing ?? initialProcessing('application/pdf')),
      status: 'queued',
      reasonCode: null,
      reason: null,
      updatedAt: new Date().toISOString(),
    };
    return HttpResponse.json(doc);
  }),

  http.post('*/api/documents/:id/:change', ({ params }) => {
    const change = String(params.change);
    if (change !== 'share' && change !== 'unshare') return undefined;
    const id = String(params.id);
    const owner = state.cases.find((c) => c.documents.some((d) => d.id === id));
    const rel = owner ? relationTo(owner, currentMockUser()) : 'none';
    if (!owner || !allows(rel, 'view')) {
      return problem(404, 'document-not-found', 'No document with this id exists.');
    }
    if (!allows(rel, 'share')) return forbidden();
    if (owner.archivedAt !== null) return caseArchived();
    const document = owner.documents.find((d) => d.id === id);
    if (!document) return problem(404, 'document-not-found', 'No document with this id exists.');
    if (change === 'share' && !document.hasFile) {
      return problem(
        422,
        'no-file',
        'This is a sample record with no stored file; it cannot be shared.',
      );
    }
    if ((document.sharedWithClientAt !== null) !== (change === 'share')) {
      document.sharedWithClientAt = change === 'share' ? new Date().toISOString() : null;
    }
    return HttpResponse.json(document);
  }),

  http.get('*/api/portal/cases', () => {
    const user = currentMockUser();
    return HttpResponse.json(
      state.cases
        .filter((c) => c.clientId === user?.clientId && c.archivedAt === null)
        .map(portalSummary),
    );
  }),

  http.get('*/api/portal/cases/:id', ({ params }) => {
    const user = currentMockUser();
    const c = state.cases.find(
      (k) => k.id === params.id && k.clientId === user?.clientId && k.archivedAt === null,
    );
    if (!c) return caseNotFound();
    const today = todayIsoDate();
    return HttpResponse.json({
      ...portalSummary(c),
      hearings: c.hearings
        .filter((h) => h.status === 'Scheduled' && h.date >= today)
        .map(({ date, time, court, purpose }) => ({ date, time, court, purpose })),
      documents: c.documents
        .filter((d) => d.sharedWithClientAt !== null)
        .map((d) => ({
          id: d.id,
          name: d.name,
          type: d.type,
          size: d.size,
          sharedOn: (d.sharedWithClientAt ?? '').slice(0, 10),
          downloadUrl: `/api/portal/documents/${d.id}/download`,
        })),
    });
  }),

  http.get('*/api/cases/:id/documents/deleted', ({ params }) => {
    const found = visibleCase(String(params.id));
    if (!found) return caseNotFound();
    if (!allows(found.rel, 'restore')) return forbidden();
    return HttpResponse.json(found.c.deletedDocuments);
  }),

  http.post('*/api/documents/:id/restore', ({ params }) => {
    const id = String(params.id);
    const owner = state.cases.find(
      (c) => c.documents.some((d) => d.id === id) || c.deletedDocuments.some((d) => d.id === id),
    );
    const rel = owner ? relationTo(owner, currentMockUser()) : 'none';
    if (!owner || !allows(rel, 'view')) {
      return problem(404, 'document-not-found', 'No document with this id exists.');
    }
    if (!allows(rel, 'restore')) return forbidden();
    if (owner.archivedAt !== null) return caseArchived();
    const deleted = owner.deletedDocuments.find((d) => d.id === id);
    if (!deleted) return HttpResponse.json(owner.documents.find((d) => d.id === id));
    if (owner.documents.some((d) => d.name.toLowerCase() === deleted.name.toLowerCase())) {
      return problem(
        409,
        'duplicate',
        `Another document named ${deleted.name} is on this case. Delete or rename it, then restore.`,
      );
    }
    const { deletedAt: _at, deletedBy: _by, ...restored } = deleted;
    owner.deletedDocuments = owner.deletedDocuments.filter((d) => d.id !== id);
    owner.documents = sortDocuments([restored, ...owner.documents]);
    owner.documentCount = owner.documents.length;
    return HttpResponse.json(restored);
  }),
];

export const server = setupServer(...handlers);
