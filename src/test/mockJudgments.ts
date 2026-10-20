/**
 * The fake judgment collection for front-end tests (SYNTHETIC data only).
 *
 * Mirrors the server's judgment routes (`server/lexflow/api/judgments.py`):
 * staff only, validation, keyword search over title and text, semantic modes
 * that answer 409 when unavailable, paging and not-found codes. Searching here
 * is a simple word match; real ranking is tested on the server.
 */
import { delay, http, HttpResponse } from 'msw';
import type { JudgmentDetail, JudgmentSearchMode } from '../types';

export interface MockJudgment {
  detail: JudgmentDetail;
  /** The text of each page (or part). */
  sections: string[];
}

interface JudgmentState {
  judgments: MockJudgment[];
  semantic: { available: boolean; reason: string | null };
  /** Make searches for this text slow (to test stale results). */
  slowQuery: string | null;
  failSearch: boolean;
}

const SOURCE = {
  key: 'lexflow-synthetic',
  name: 'LexFlow synthetic test judgments',
  termsUrl: 'https://terms.lexflow.invalid/synthetic',
  termsCheckedOn: '2026-10-20',
  termsCheckedBy: 'LexFlow developers',
  permittedUse: 'Invented for automated tests only. Not real judgments; never cite.',
  synthetic: true,
};

/** A SYNTHETIC judgment for tests. */
export function syntheticJudgment(
  n: number,
  title: string,
  sections: string[],
  extra: Partial<JudgmentDetail> = {},
): MockJudgment {
  const year = 2010 + (n % 15);
  return {
    sections,
    detail: {
      id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
      title,
      court: 'SYNTHETIC High Court (test fixture)',
      citation: `(SYN) ${year} TEST ${100 + n}`,
      decisionDate: `${year}-03-0${(n % 9) + 1}`,
      year,
      practiceAreas: ['Tenancy'],
      sourceName: SOURCE.name,
      sourceUrl: `https://judgments.lexflow.invalid/syn-${n}`,
      synthetic: true,
      bench: 'SYNTHETIC J.',
      source: SOURCE,
      pageCount: sections.length,
      sectionCount: sections.length,
      charCount: sections.join('').length,
      extractor: 'pypdf 6.21.1',
      importedAt: '2026-10-20T09:00:00Z',
      ...extra,
    },
  };
}

let state: JudgmentState = fresh();

function fresh(): JudgmentState {
  return {
    judgments: [],
    semantic: { available: false, reason: 'Semantic search is off: embeddings are disabled.' },
    slowQuery: null,
    failSearch: false,
  };
}

export function resetMockJudgments(): void {
  state = fresh();
}

export function mockSetJudgments(judgments: MockJudgment[]): void {
  state.judgments = judgments;
}

export function mockJudgmentOptions(options: Partial<Omit<JudgmentState, 'judgments'>>): void {
  state = { ...state, ...options };
}

function problem(status: number, code: string, detail: string) {
  return HttpResponse.json(
    { type: 'about:blank', title: 'Problem', status, code, detail },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

const summary = ({ detail }: MockJudgment) => ({
  id: detail.id,
  title: detail.title,
  court: detail.court,
  citation: detail.citation,
  decisionDate: detail.decisionDate,
  year: detail.year,
  practiceAreas: detail.practiceAreas,
  sourceName: detail.sourceName,
  sourceUrl: detail.sourceUrl,
  synthetic: detail.synthetic,
});

function newestFirst(list: MockJudgment[]) {
  return [...list].sort((a, b) =>
    (b.detail.decisionDate ?? '').localeCompare(a.detail.decisionDate ?? ''),
  );
}

/** Handlers; `staff` refuses anyone who may not use staff routes (as the server does). */
export function judgmentHandlers(staff: () => Response | undefined) {
  return [
    http.get('*/api/judgments/facets', () => {
      const refused = staff();
      if (refused) return refused;
      const years = state.judgments.map((j) => j.detail.year).filter((y): y is number => !!y);
      return HttpResponse.json({
        total: state.judgments.length,
        synthetic: state.judgments.filter((j) => j.detail.synthetic).length,
        indexed: state.semantic.available ? state.judgments.length : 0,
        courts: [...new Set(state.judgments.map((j) => j.detail.court))].sort(),
        yearMin: years.length ? Math.min(...years) : null,
        yearMax: years.length ? Math.max(...years) : null,
        modes: {
          keyword: true,
          semantic: state.semantic.available,
          hybrid: state.semantic.available,
          unavailableReason: state.semantic.available ? null : state.semantic.reason,
          model: state.semantic.available ? 'BAAI/bge-small-en-v1.5@5c38ec7c405e' : null,
        },
      });
    }),

    http.get('*/api/judgments/search', async ({ request }) => {
      const refused = staff();
      if (refused) return refused;
      const url = new URL(request.url);
      const q = (url.searchParams.get('q') ?? '').trim();
      const mode = (url.searchParams.get('mode') ?? 'keyword') as JudgmentSearchMode;
      const page = Number(url.searchParams.get('page') ?? 1);
      const pageSize = Number(url.searchParams.get('pageSize') ?? 10);
      if (!q) return problem(422, 'query-empty', 'Type something to search for.');
      if (q.length > 300) return problem(422, 'validation', 'At most 300 characters.');
      if (mode !== 'keyword' && !state.semantic.available) {
        return problem(409, 'semantic-search-unavailable', state.semantic.reason ?? 'Off.');
      }
      if (state.failSearch) return problem(503, 'unavailable', 'The search service failed.');
      if (state.slowQuery && q === state.slowQuery) await delay(400);
      const words = q.toLowerCase().split(/\s+/);
      const hits = newestFirst(state.judgments).flatMap((j) => {
        const index = j.sections.findIndex((text) =>
          words.every((w) => `${j.detail.title} ${text}`.toLowerCase().includes(w)),
        );
        if (index < 0) return [];
        const text = j.sections[index];
        return [
          {
            judgment: summary(j),
            score: 1,
            passage: {
              chunkId: `${j.detail.id}-chunk-${index + 1}`,
              sectionNumber: index + 1,
              pageNumber: index + 1,
              charStart: 0,
              charEnd: text.length,
              text,
            },
          },
        ];
      });
      return HttpResponse.json({
        mode,
        model: mode === 'keyword' ? null : 'BAAI/bge-small-en-v1.5@5c38ec7c405e',
        total: hits.length,
        maxResults: 100,
        page,
        pageSize,
        results: hits.slice((page - 1) * pageSize, page * pageSize),
      });
    }),

    http.get('*/api/judgments', ({ request }) => {
      const refused = staff();
      if (refused) return refused;
      const url = new URL(request.url);
      const page = Number(url.searchParams.get('page') ?? 1);
      const pageSize = Number(url.searchParams.get('pageSize') ?? 20);
      const court = url.searchParams.get('court');
      const list = newestFirst(state.judgments).filter((j) => !court || j.detail.court === court);
      return HttpResponse.json({
        items: list.slice((page - 1) * pageSize, page * pageSize).map(summary),
        total: list.length,
        page,
        pageSize,
      });
    }),

    http.get('*/api/judgments/:id/text', ({ params, request }) => {
      const refused = staff();
      if (refused) return refused;
      const found = state.judgments.find((j) => j.detail.id === params.id);
      if (!found) return problem(404, 'judgment-not-found', 'No judgment with this id exists.');
      const number = Number(new URL(request.url).searchParams.get('section') ?? 1);
      if (number < 1 || number > found.sections.length) {
        return problem(
          404,
          'section-not-found',
          `This judgment has ${found.sections.length} pages.`,
        );
      }
      return HttpResponse.json({
        judgmentId: found.detail.id,
        title: found.detail.title,
        synthetic: found.detail.synthetic,
        pageCount: found.detail.pageCount,
        sectionCount: found.sections.length,
        section: { number, pageNumber: number, text: found.sections[number - 1] },
      });
    }),

    http.get('*/api/judgments/:id', ({ params }) => {
      const refused = staff();
      if (refused) return refused;
      const found = state.judgments.find((j) => j.detail.id === params.id);
      if (!found) return problem(404, 'judgment-not-found', 'No judgment with this id exists.');
      return HttpResponse.json(found.detail);
    }),
  ];
}
