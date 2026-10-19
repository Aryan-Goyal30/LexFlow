import { describe, expect, it } from 'vitest';
import { formatFileSize, isPastDate, todayIsoDate } from './format';
import { checkFiles, isSupportedFileName } from './documentFiles';
import { safeReturnPath, HOME_PATH } from './paths';
import { validateNewCase, type NewCaseForm } from './validateNewCase';

const file = (name: string, content = 'content') => new File([content], name);

describe('dates', () => {
  it('formats today in local time, not UTC', () => {
    // 00:30 local time on 5 March; in UTC this may still be 4 March.
    expect(todayIsoDate(new Date(2026, 2, 5, 0, 30))).toBe('2026-03-05');
  });

  it('treats only dates before today as past', () => {
    const now = new Date(2026, 9, 14, 12, 0);
    expect(isPastDate('2026-10-13', now)).toBe(true);
    expect(isPastDate('2026-10-14', now)).toBe(false);
    expect(isPastDate('2026-10-15', now)).toBe(false);
  });
});

describe('document rules', () => {
  it('accepts PDF, Word, text and common images, case-insensitively', () => {
    for (const name of ['a.pdf', 'b.DOCX', 'c.doc', 'd.txt', 'e.PNG', 'f.jpeg', 'g.webp']) {
      expect(isSupportedFileName(name)).toBe(true);
    }
    for (const name of ['virus.exe', 'archive.zip', 'noextension', 'sheet.xlsx', 'vector.svg']) {
      expect(isSupportedFileName(name)).toBe(false);
    }
  });

  it('rejects unsupported, empty and duplicate files with a reason', () => {
    const result = checkFiles(
      [
        file('Brief.pdf'),
        file('setup.exe'),
        file('Empty.pdf', ''),
        file('Existing.pdf'),
        file('brief.PDF'), // same name as the first file in this selection
      ],
      ['existing.pdf'],
    );

    expect(result.accepted.map((f) => f.name)).toEqual(['Brief.pdf']);
    expect(result.rejected).toEqual([
      { name: 'setup.exe', reason: 'unsupported-type' },
      { name: 'Empty.pdf', reason: 'empty' },
      { name: 'Existing.pdf', reason: 'duplicate' },
      { name: 'brief.PDF', reason: 'duplicate' },
    ]);
  });

  it('returns nothing for an empty selection', () => {
    expect(checkFiles([], [])).toEqual({ accepted: [], rejected: [] });
  });
});

describe('safeReturnPath', () => {
  it('keeps paths inside the app', () => {
    expect(safeReturnPath('/app/cases/case-1005?tab=research')).toBe(
      '/app/cases/case-1005?tab=research',
    );
  });

  it('falls back to the case list for anything else', () => {
    for (const from of [undefined, null, 42, '/', '//evil.example', 'https://evil.example']) {
      expect(safeReturnPath(from)).toBe(HOME_PATH);
    }
  });
});

describe('validateNewCase', () => {
  const today = '2026-10-14';
  const clientIds = ['client-1', 'client-2'];
  const advocateIds = ['advocate-1'];
  const valid: NewCaseForm = {
    title: 'Test Matter v. Other Party',
    clientId: 'client-1',
    practiceArea: 'Civil',
    status: 'Open',
    priority: 'Medium',
    leadAdvocateId: 'advocate-1',
    courtName: '',
    opposingParty: '',
    nextHearing: '',
    description: 'A summary long enough to pass.',
  };

  it('accepts a complete form', () => {
    expect(validateNewCase(valid, clientIds, advocateIds, today)).toEqual({});
  });

  it('flags each invalid field', () => {
    const errors = validateNewCase(
      {
        ...valid,
        title: '  ab  ',
        clientId: 'no-such-client',
        leadAdvocateId: 'no-such-advocate',
        description: 'short',
        nextHearing: '2026-10-13',
      },
      clientIds,
      advocateIds,
      today,
    );
    expect(Object.keys(errors).sort()).toEqual([
      'clientId',
      'description',
      'leadAdvocateId',
      'nextHearing',
      'title',
    ]);
    expect(errors.nextHearing).toMatch(/cannot be in the past/);
  });

  it('allows a hearing today', () => {
    expect(
      validateNewCase({ ...valid, nextHearing: today }, clientIds, advocateIds, today),
    ).toEqual({});
  });
});

describe('formatFileSize', () => {
  it('matches the server rule', () => {
    expect(formatFileSize(512)).toBe('512 B');
    expect(formatFileSize(1536)).toBe('2 KB');
    expect(formatFileSize(3.2 * 1024 * 1024)).toBe('3.2 MB');
  });
});
