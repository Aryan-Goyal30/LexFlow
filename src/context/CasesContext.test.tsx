import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CasesProvider, useCases } from './CasesContext';
import { mockCases, mockClients } from '../data/mockData';
import { nextCaseNumber } from '../lib/format';
import type { Case, CaseDocument, NewCaseInput } from '../types';

const input: NewCaseInput = {
  title: '  Test Matter v. Other Party  ',
  clientId: mockClients[1].id,
  practiceArea: 'Civil',
  status: 'Open',
  priority: 'High',
  leadAttorney: 'Meera Nair',
  courtName: '  ',
  opposingParty: 'Other Party',
  description: '  A summary of the test matter.  ',
  nextHearing: '2099-01-15',
};

function renderStore() {
  return renderHook(() => useCases(), { wrapper: CasesProvider });
}

describe('CasesContext.addCase', () => {
  it('returns the same case object it adds to the top of the list', () => {
    const { result } = renderStore();
    let created!: Case;
    act(() => {
      created = result.current.addCase(input);
    });

    expect(result.current.cases).toHaveLength(mockCases.length + 1);
    expect(result.current.cases[0]).toBe(created);
    expect(result.current.getCaseById(created.id)).toBe(created);
  });

  it('cleans the input and fills derived fields', () => {
    const { result } = renderStore();
    let created!: Case;
    act(() => {
      created = result.current.addCase(input);
    });

    expect(created.title).toBe('Test Matter v. Other Party');
    expect(created.description).toBe('A summary of the test matter.');
    expect(created.courtName).toBeUndefined();
    expect(created.clientName).toBe(mockClients[1].name);
    expect(created.caseNumber).toBe(nextCaseNumber(mockCases.map((c) => c.caseNumber)));
    expect(created.hearings).toEqual([
      expect.objectContaining({ date: '2099-01-15', purpose: 'First listing' }),
    ]);
    expect(created.timeline).toEqual([expect.objectContaining({ label: 'Matter opened' })]);
  });

  it('gives cases created back to back distinct ids and case numbers', () => {
    const { result } = renderStore();
    let first!: Case;
    let second!: Case;
    // Both calls use the same render's state, as a double submission would.
    act(() => {
      first = result.current.addCase(input);
      second = result.current.addCase(input);
    });

    expect(first.id).not.toBe(second.id);
    expect(first.caseNumber).not.toBe(second.caseNumber);
    expect(result.current.cases.slice(0, 2)).toEqual([second, first]);
    const ids = result.current.cases.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('CasesContext documents', () => {
  it('attaches files and revokes the object URL when a document is removed', () => {
    const revoke = vi.spyOn(URL, 'revokeObjectURL');
    const { result } = renderStore();
    const caseId = mockCases[0].id;
    const before = mockCases[0].documents.length;

    let added: CaseDocument[] = [];
    act(() => {
      added = result.current.addDocuments(caseId, [new File(['x'], 'Reply.pdf')]);
    });
    const doc = added[0];
    expect(doc.url).toMatch(/^blob:/);
    expect(result.current.getCaseById(caseId)?.documents).toHaveLength(before + 1);

    act(() => {
      result.current.removeDocument(caseId, doc.id);
    });
    expect(revoke).toHaveBeenCalledTimes(1);
    expect(revoke).toHaveBeenCalledWith(doc.url);
    expect(result.current.getCaseById(caseId)?.documents).toHaveLength(before);
  });

  it('does not revoke anything when removing a sample record without a file', () => {
    const revoke = vi.spyOn(URL, 'revokeObjectURL');
    const { result } = renderStore();
    const sample = mockCases[0].documents[0];

    act(() => {
      result.current.removeDocument(mockCases[0].id, sample.id);
    });
    expect(revoke).not.toHaveBeenCalled();
  });
});
