import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL, mockApiState, mockSetProcessing, mockSetText } from '../test/mockApi';

// Viewing extracted text and retrying a failed extraction. The server enforces
// access and serves the text (server/tests/test_document_text.py).

const SATTVIK = 'case-1005';
const PAGES = [
  'FICTIONAL page one: the petitioner states the facts.',
  'FICTIONAL page two: the respondent replied on 3 March 2026.',
  'FICTIONAL page three: prayer for relief.',
];

async function uploadPdf(name: string) {
  const { user, url } = renderApp(`/app/cases/${SATTVIK}?tab=documents`, { as: ARYAN_EMAIL });
  await user.upload(
    await screen.findByLabelText('Choose files to attach'),
    new File(['%PDF-1.4\n%%EOF\n'], name, { type: 'application/pdf' }),
  );
  await screen.findByRole('link', { name: `Open ${name}` });
  const doc = mockApiState()
    .cases.find((c) => c.id === SATTVIK)
    ?.documents.find((d) => d.name === name);
  if (!doc) throw new Error('not uploaded');
  return { user, url, id: doc.id };
}

const row = (name: string) =>
  within(screen.getByRole('list', { name: 'Case documents' }))
    .getByText(name)
    .closest('li') as HTMLElement;

describe('the extracted text', () => {
  it('opens from the Documents tab and moves page by page', async () => {
    const { user, url, id } = await uploadPdf('Petition.pdf');
    mockSetText(id, PAGES);
    await user.click(
      await screen.findByRole('link', { name: 'View the text of Petition.pdf' }, { timeout: 6000 }),
    );

    expect(await screen.findByRole('heading', { name: 'Petition.pdf' })).toBeVisible();
    expect(screen.getByRole('article', { name: 'Page 1 of 3' })).toHaveTextContent(PAGES[0]);
    await user.click(screen.getByRole('link', { name: /Next page/ }));
    expect(await screen.findByRole('article', { name: 'Page 2 of 3' })).toHaveTextContent(PAGES[1]);
    expect(url()).toBe(`/app/cases/${SATTVIK}/documents/${id}/text?section=2`);
    await user.selectOptions(screen.getByLabelText('Go to page'), '3');
    expect(await screen.findByRole('article', { name: 'Page 3 of 3' })).toHaveTextContent(PAGES[2]);
    expect(screen.queryByRole('link', { name: /Next page/ })).toBeNull();
    expect(screen.getByText(/Check it against the original document/)).toBeVisible();
  });

  it('shows parts, not pages, for documents without pages', async () => {
    const { id } = await uploadPdf('Notes.pdf');
    mockSetText(id, ['FICTIONAL part one.', 'FICTIONAL part two.'], { pages: false });
    renderApp(`/app/cases/${SATTVIK}/documents/${id}/text`, { as: ARYAN_EMAIL });
    expect((await screen.findAllByRole('article', { name: 'Part 1 of 2' }))[0]).toBeVisible();
    expect(screen.getAllByText(/have no fixed pages/)[0]).toBeVisible();
  });

  it('says plainly when a page has no text', async () => {
    const { id } = await uploadPdf('Mixed.pdf');
    mockSetText(id, ['FICTIONAL first.', '']);
    renderApp(`/app/cases/${SATTVIK}/documents/${id}/text?section=2`, { as: ARYAN_EMAIL });
    expect((await screen.findAllByText(/No text was found on this page/))[0]).toBeVisible();
  });

  it('explains why the text is not available yet', async () => {
    const { id } = await uploadPdf('Waiting.pdf');
    renderApp(`/app/cases/${SATTVIK}/documents/${id}/text`, { as: ARYAN_EMAIL });
    expect((await screen.findAllByText('The text is not available'))[0]).toBeVisible();
    expect(screen.getAllByText(/waiting to be processed/)[0]).toBeVisible();
  });
});

describe('retrying a failed extraction', () => {
  it('queues the document again', async () => {
    const { user, id } = await uploadPdf('Scan.pdf');
    mockSetProcessing(id, {
      status: 'failed',
      reasonCode: 'no-text-layer',
      reason: 'This PDF has no text layer (it may be a scan).',
    });
    const retry = await screen.findByRole(
      'button',
      { name: 'Try extracting the text of Scan.pdf again' },
      { timeout: 6000 },
    );
    // No text to view until it has been extracted.
    expect(screen.queryByRole('link', { name: 'View the text of Scan.pdf' })).toBeNull();
    await user.click(retry);
    expect(await screen.findByText('Scan.pdf will be processed again.')).toBeVisible();
    await waitFor(() => expect(row('Scan.pdf')).toHaveTextContent('Waiting for text extraction'));
  });

  it('is not offered on an archived case', async () => {
    const { id } = await uploadPdf('Scan.pdf');
    mockSetProcessing(id, { status: 'failed', reasonCode: 'unreadable', reason: 'Damaged.' });
    const stored = mockApiState().cases.find((c) => c.id === SATTVIK);
    if (stored) stored.archivedAt = '2026-10-20T09:00:00Z';
    renderApp(`/app/cases/${SATTVIK}?tab=documents`, { as: ARYAN_EMAIL });
    expect((await screen.findAllByText(/Text extraction failed: Damaged\./))[0]).toBeVisible();
    expect(screen.queryByRole('button', { name: /Try extracting/ })).toBeNull();
  });
});
