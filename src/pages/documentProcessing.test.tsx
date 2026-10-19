import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { mockApiState, mockSetProcessing } from '../test/mockApi';

// Text-extraction status in the Documents tab. The server sets it
// (server/tests/test_extraction_queue.py); these tests check what is shown.

const SATTVIK = 'case-1005';

const pdf = (name = 'Brief.pdf') =>
  new File(['%PDF-1.4\n%%EOF\n'], name, { type: 'application/pdf' });

const row = (name: string) =>
  within(screen.getByRole('list', { name: 'Case documents' }))
    .getByText(name)
    .closest('li') as HTMLElement;

function uploadedId(name: string): string {
  const doc = mockApiState()
    .cases.find((c) => c.id === SATTVIK)
    ?.documents.find((d) => d.name === name);
  if (!doc) throw new Error(`no document ${name}`);
  return doc.id;
}

describe('text extraction status', () => {
  it('shows a new upload waiting, then follows it to ready without a reload', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.upload(await screen.findByLabelText('Choose files to attach'), pdf());
    await waitFor(() => expect(row('Brief.pdf')).toHaveTextContent('Waiting for text extraction'));

    mockSetProcessing(uploadedId('Brief.pdf'), {
      status: 'ready',
      pageCount: 3,
      sectionCount: 3,
      chunkCount: 4,
    });
    // The page refreshes the case by itself while a document is pending.
    await waitFor(() => expect(row('Brief.pdf')).toHaveTextContent('Text extracted · 3 pages'), {
      timeout: 6000,
    });
  });

  it('counts parts, not pages, for documents without pages', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.upload(
      await screen.findByLabelText('Choose files to attach'),
      new File(['Some notes.'], 'Notes.txt', { type: 'text/plain' }),
    );
    await waitFor(() => expect(row('Notes.txt')).toBeVisible());
    mockSetProcessing(uploadedId('Notes.txt'), { status: 'ready', sectionCount: 1 });
    await waitFor(() => expect(row('Notes.txt')).toHaveTextContent('Text extracted · 1 part'), {
      timeout: 6000,
    });
  });

  it('shows why extraction failed', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.upload(await screen.findByLabelText('Choose files to attach'), pdf('Scan.pdf'));
    await waitFor(() => expect(row('Scan.pdf')).toBeVisible());
    mockSetProcessing(uploadedId('Scan.pdf'), {
      status: 'failed',
      reasonCode: 'no-text-layer',
      reason: 'This PDF has no text layer (it may be a scan). OCR is not available.',
    });
    await waitFor(
      () =>
        expect(row('Scan.pdf')).toHaveTextContent(
          'Text extraction failed: This PDF has no text layer (it may be a scan).',
        ),
      { timeout: 6000 },
    );
  });

  it('explains why images are not processed', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.upload(
      await screen.findByLabelText('Choose files to attach'),
      new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'Photo.png', { type: 'image/png' }),
    );
    await waitFor(() =>
      expect(row('Photo.png')).toHaveTextContent(
        'Text is not extracted from images (OCR is not available).',
      ),
    );
  });

  it('shows no status for sample records, which have no file', async () => {
    renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    const sample = row((await screen.findByText('Cease and Desist Notice.pdf')).textContent ?? '');
    expect(sample).not.toHaveTextContent(/extract/i);
  });
});
