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
import {
  advocates as sampleAdvocates,
  currentUser,
  mockCases,
  mockClients,
} from '../data/mockData';
import { formatFileSize, todayIsoDate } from '../lib/format';
import { ACCEPTED_TYPES_LABEL } from '../lib/documentFiles';
import type {
  Advocate,
  Case,
  CaseDocument,
  CaseSummary,
  Client,
  NewCaseInput,
  Problem,
  UpcomingHearing,
} from '../types';

interface StoredFile {
  bytes: Uint8Array;
  contentType: string;
}

interface State {
  clients: Client[];
  advocates: Advocate[];
  cases: Case[];
  files: Map<string, StoredFile>;
  nextId: number;
}

const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-');

export const advocateId = (name: string) => `advocate-${slug(name)}`;

function nextHearing(c: Pick<Case, 'hearings'>, today: string): string | null {
  const dates = c.hearings.map((h) => h.date).sort();
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
  const advocates: Advocate[] = sampleAdvocates.map((name) => ({
    id: advocateId(name),
    name,
    email: name === currentUser.name ? currentUser.email : null,
    isSample: true,
  }));
  const cases: Case[] = mockCases.map((c) => {
    const detail: Case = {
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
          isSample: true,
        })),
      ),
      hearings: c.hearings.map((h) => ({ ...h, isSample: true })),
      timeline: c.timeline.map((t) => ({ ...t, actor: null, isSample: true })),
    };
    detail.nextHearing = nextHearing(detail, today);
    return detail;
  });
  return {
    clients: mockClients.map((c) => ({ ...c, company: c.company ?? null, isSample: true })),
    advocates,
    cases,
    files: new Map(),
    nextId: 1,
  };
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
  return found;
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

function summary(c: Case): CaseSummary {
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
    isSample: c.isSample,
  };
}

const findCase = (id: string) => state.cases.find((c) => c.id === id);

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

export const handlers = [
  http.get('*/api/cases', () =>
    HttpResponse.json(
      [...state.cases].sort((a, b) => b.openedOn.localeCompare(a.openedOn)).map(summary),
    ),
  ),

  http.get('*/api/cases/:id', ({ params }) => {
    const c = findCase(String(params.id));
    return c
      ? HttpResponse.json(c)
      : problem(404, 'case-not-found', 'No case with this id exists.');
  }),

  http.post('*/api/cases', async ({ request }) => {
    const input = (await request.json()) as NewCaseInput;
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
    const created: Case = {
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
          actor: null,
          isSample: false,
        },
      ],
    };
    state.cases.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.get('*/api/clients', () =>
    HttpResponse.json([...state.clients].sort((a, b) => a.name.localeCompare(b.name))),
  ),

  http.get('*/api/advocates', () =>
    HttpResponse.json([...state.advocates].sort((a, b) => a.name.localeCompare(b.name))),
  ),

  http.get('*/api/hearings/upcoming', ({ request }) => {
    const limit = Number(new URL(request.url).searchParams.get('limit') ?? 5);
    const today = todayIsoDate();
    const upcoming: UpcomingHearing[] = state.cases
      .flatMap((c) =>
        c.hearings.map((h) => ({
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
    const c = findCase(String(params.id));
    if (!c) return problem(404, 'case-not-found', 'No case with this id exists.');
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
    if (!owner) return problem(404, 'document-not-found', 'No document with this id exists.');
    owner.documents = owner.documents.filter((d) => d.id !== id);
    owner.documentCount = owner.documents.length;
    state.files.delete(id);
    return new HttpResponse(null, { status: 204 });
  }),
];

export const server = setupServer(...handlers);
