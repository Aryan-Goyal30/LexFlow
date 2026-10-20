import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { mockApiState, problem, server } from '../test/mockApi';

// A sample case with documents, court and opposing party.
const CASE_URL = '/app/cases/case-1005';

const tab = (name: RegExp) => screen.getByRole('tab', { name });

/** Render the workspace and wait until the case has loaded. */
async function openCase(path = CASE_URL) {
  const app = renderApp(path);
  await screen.findByRole('heading', { level: 1, name: /Sattvik Foods/ });
  return app;
}

describe('Loading the case', () => {
  it('shows a loading state, then the case from the API', async () => {
    renderApp(CASE_URL);

    expect(screen.getByRole('status')).toHaveTextContent('Loading the case');
    expect(
      await screen.findByRole('heading', { level: 1, name: /Sattvik Foods/ }),
    ).toBeInTheDocument();
    expect(screen.getByText('Sample')).toBeInTheDocument(); // fictional data is labelled
  });

  it('says so when the API has no such case', async () => {
    renderApp('/app/cases/no-such-case');

    expect(await screen.findByRole('heading', { name: 'Case not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to Cases' })).toHaveAttribute(
      'href',
      '/app/cases',
    );
  });

  it('offers a retry when the server fails', async () => {
    server.use(http.get('*/api/cases/:id', () => problem(500, 'internal-error', 'Boom.')));
    const { user } = renderApp(CASE_URL);

    expect(await screen.findByText("Couldn't load the case")).toBeInTheDocument();
    server.resetHandlers();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: /Sattvik Foods/ }),
    ).toBeInTheDocument();
  });

  it('keeps the case on screen when a later refresh fails', async () => {
    const { queryClient, user } = await openCase();
    server.use(
      http.get('*/api/cases/:id', () => problem(500, 'internal-error', 'Refresh failed.')),
    );

    await act(() => queryClient.invalidateQueries());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Couldn't refresh, so this may be out of date. Refresh failed.",
    );
    expect(screen.getByRole('heading', { level: 1, name: /Sattvik Foods/ })).toBeInTheDocument();

    server.resetHandlers();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('shows hearing times as unknown when the court has not set one', async () => {
    mockApiState().cases.find((c) => c.id === 'case-1005')!.hearings[0].time = null;
    await openCase();
    expect(screen.getByText(/time to be confirmed/)).toBeInTheDocument();
  });
});

describe('Workspace tabs and the URL', () => {
  it('puts the selected tab in the query string', async () => {
    const { url, user } = await openCase();

    expect(tab(/Overview/)).toHaveAttribute('aria-selected', 'true');
    await user.click(tab(/Documents/));
    expect(url()).toBe(`${CASE_URL}?tab=documents`);
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName(/Documents/);

    await user.click(tab(/Overview/));
    expect(url()).toBe(CASE_URL);
  });

  it('lets Back and Forward step through tabs without duplicate entries', async () => {
    const { url, user, go } = await openCase();

    await user.click(tab(/Documents/));
    await user.click(tab(/Documents/)); // re-selecting adds no history entry
    await user.click(tab(/AI Analysis/));

    go(-1);
    expect(url()).toBe(`${CASE_URL}?tab=documents`);
    expect(tab(/Documents/)).toHaveAttribute('aria-selected', 'true');

    go(-1);
    expect(url()).toBe(CASE_URL);
    expect(tab(/Overview/)).toHaveAttribute('aria-selected', 'true');

    go(1);
    expect(url()).toBe(`${CASE_URL}?tab=documents`);
  });

  it('opens a tab directly from the URL', async () => {
    await openCase(`${CASE_URL}?tab=research`);
    expect(tab(/Research/)).toHaveAttribute('aria-selected', 'true');
  });

  it('shows Overview for an unknown tab and removes it from the URL', async () => {
    const { url } = await openCase(`${CASE_URL}?tab=bogus`);
    expect(tab(/Overview/)).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => expect(url()).toBe(CASE_URL));
  });

  it('moves focus between tabs with the arrow keys without selecting them', async () => {
    const { url, user } = await openCase();

    tab(/Overview/).focus();
    await user.keyboard('{ArrowRight}');
    expect(tab(/Documents/)).toHaveFocus();
    expect(url()).toBe(CASE_URL);

    await user.keyboard('{End}');
    expect(tab(/Research/)).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(url()).toBe(`${CASE_URL}?tab=research`);
  });
});

describe('AI Analysis while no service is connected; Research on the judgment collection', () => {
  it('marks only AI Analysis as not connected', async () => {
    await openCase();
    expect(tab(/AI Analysis/)).toHaveTextContent('Not connected');
    expect(tab(/Research/)).not.toHaveTextContent('Not connected');
  });

  it('shows the unavailable state on AI Analysis and no results', async () => {
    await openCase(`${CASE_URL}?tab=analysis`);

    expect(screen.getByText('AI analysis is not connected yet')).toBeInTheDocument();
    const analyse = screen.getByRole('button', { name: /Analyse case/ });
    expect(analyse).toBeDisabled();
    expect(analyse).toHaveAccessibleDescription(/no AI service is connected/);
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Relevant Precedents/)).not.toBeInTheDocument();
    // The inputs panel is real case data from the API.
    expect(screen.getByText('4 on file, 0 with a stored file')).toBeInTheDocument();
  });

  it('says plainly when the judgment collection is empty, with no results', async () => {
    await openCase(`${CASE_URL}?tab=research`);

    expect(await screen.findByText('The judgment collection is empty')).toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });
});

describe('Documents tab', () => {
  const pdf = (name = 'Rejoinder.pdf', content = '%PDF-1.4 test') =>
    new File([content], name, { type: 'application/pdf' });
  const openDocuments = () => openCase(`${CASE_URL}?tab=documents`);
  const picker = () => screen.getByLabelText('Choose files to attach');

  it('uploads a file to the server and lists it with an Open link', async () => {
    const { user } = await openDocuments();

    await user.upload(picker(), pdf());

    expect(await screen.findByText('Added Rejoinder.pdf.')).toBeInTheDocument();
    const open = await screen.findByRole('link', { name: 'Open Rejoinder.pdf' });
    expect(open.getAttribute('href')).toMatch(
      /^http:\/\/[^/]+\/api\/documents\/doc-new-\d+\/download$/,
    );
    await waitFor(() => expect(tab(/Documents/)).toHaveTextContent('5'));
    expect(mockApiState().files.size).toBe(1); // stored by the server
  });

  it('shows progress while uploading', async () => {
    server.use(
      http.post('*/api/cases/:id/documents', async () => {
        await delay(150);
        return problem(415, 'content-mismatch', 'slow');
      }),
    );
    const { user } = await openDocuments();

    await user.upload(picker(), [pdf('One.pdf'), pdf('Two.pdf')]);

    expect(await screen.findByText(/Uploading One\.pdf \(1 of 2\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Choose files' })).toBeDisabled();
    expect(await screen.findByText('2 files were not added:')).toBeInTheDocument();
  });

  it('checks files in the browser before uploading', async () => {
    const { user } = await openDocuments();

    await user.upload(picker(), [new File(['MZ'], 'setup.exe'), new File([''], 'Empty.pdf')]);

    const status = await screen.findByText('2 files were not added:');
    const list = status.parentElement as HTMLElement;
    expect(list).toHaveTextContent('setup.exe is not a supported file type');
    expect(list).toHaveTextContent('Empty.pdf is empty');
    expect(mockApiState().files.size).toBe(0); // never sent
  });

  it('shows the server reason when the server rejects a file', async () => {
    const { user } = await openDocuments();

    // Passes the browser checks, but its contents are not a PDF.
    await user.upload(picker(), pdf('Forged.pdf', 'not really a pdf'));

    expect(
      await screen.findByText("The contents of Forged.pdf don't match its file type."),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Open Forged.pdf' })).not.toBeInTheDocument();
  });

  it('applies the same rules to drag-and-drop', async () => {
    await openDocuments();

    fireEvent.drop(screen.getByTestId('document-drop-zone'), {
      dataTransfer: {
        files: [
          new File(['MZ'], 'setup.exe'),
          new File(['text'], 'Notes.txt'),
          // Already attached to this sample case.
          pdf('Cease and Desist Notice.pdf'),
        ],
      },
    });

    expect(await screen.findByText('Added Notes.txt.')).toBeInTheDocument();
    const status = screen.getByText('2 files were not added:').parentElement as HTMLElement;
    expect(status).toHaveTextContent('setup.exe is not a supported file type');
    expect(status).toHaveTextContent('Cease and Desist Notice.pdf is already attached');
  });

  it('ignores an empty selection', async () => {
    await openDocuments();
    fireEvent.change(picker(), { target: { files: [] } });
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('removes a document on the server', async () => {
    const { user } = await openDocuments();
    await user.upload(picker(), pdf());
    await screen.findByRole('link', { name: 'Open Rejoinder.pdf' });

    await user.click(screen.getByRole('button', { name: 'Remove Rejoinder.pdf' }));

    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'Open Rejoinder.pdf' })).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText('Removed Rejoinder.pdf. It can be restored from Deleted Documents below.'),
    ).toBeVisible();
    // Deletion is soft: the document and its file are kept, ready to restore.
    const deleted = await screen.findByRole('list', { name: 'Deleted documents' });
    expect(within(deleted).getByText('Rejoinder.pdf')).toBeVisible();
    expect(mockApiState().files.size).toBe(1);
  });

  it('shows pending and error states when removal fails', async () => {
    server.use(
      http.delete('*/api/documents/:id', async () => {
        await delay(100);
        return problem(500, 'internal-error', 'Something went wrong on the server.');
      }),
    );
    const { user } = await openDocuments();

    await user.click(screen.getByRole('button', { name: 'Remove Cease and Desist Notice.pdf' }));

    expect(
      screen.getByRole('button', { name: 'Removing Cease and Desist Notice.pdf' }),
    ).toBeDisabled();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Cease and Desist Notice.pdf was not removed. Something went wrong on the server.',
    );
    expect(screen.getByText('Cease and Desist Notice.pdf')).toBeInTheDocument();
  });

  it('labels sample documents that have no file behind them', async () => {
    await openDocuments();
    const item = screen.getByText('Cease and Desist Notice.pdf').closest('li');
    expect(item).not.toBeNull();
    expect(within(item as HTMLElement).getByText(/sample record, no file attached/)).toBeVisible();
    expect(
      within(item as HTMLElement).queryByRole('link', { name: /Open/ }),
    ).not.toBeInTheDocument();
  });

  it('reports a network failure for a file that could not be sent', async () => {
    server.use(http.post('*/api/cases/:id/documents', () => HttpResponse.error()));
    const { user } = await openDocuments();

    await user.upload(picker(), pdf());

    expect(await screen.findByText(/Can't reach the LexFlow server/)).toBeInTheDocument();
  });

  it('names the file when the server refuses one file of several', async () => {
    server.use(
      http.post('*/api/cases/:id/documents', async ({ request }) => {
        const file = (await request.clone().formData()).get('file') as File;
        if (file.name === 'Big.pdf') {
          // The server's size message doesn't name the file.
          return problem(413, 'too-large', 'This file is larger than the 25 MB upload limit.');
        }
        return undefined; // the normal fake API stores the others
      }),
    );
    const { user } = await openDocuments();

    await user.upload(picker(), [pdf('Small.pdf'), pdf('Big.pdf'), pdf('Other.pdf')]);

    const summary = (await screen.findByText('One file was not added:'))
      .parentElement as HTMLElement;
    expect(within(summary).getByRole('listitem')).toHaveTextContent(
      'Big.pdf: This file is larger than the 25 MB upload limit.',
    );
    expect(screen.getByText('Added 2 documents.')).toBeInTheDocument();
  });

  it('names each file that could not be sent when the server is unreachable', async () => {
    server.use(http.post('*/api/cases/:id/documents', () => HttpResponse.error()));
    const { user } = await openDocuments();

    await user.upload(picker(), [pdf('One.pdf'), pdf('Two.pdf')]);

    const summary = (await screen.findByText('2 files were not added:'))
      .parentElement as HTMLElement;
    const items = within(summary).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent(/^One\.pdf: Can't reach the LexFlow server/);
    expect(items[1]).toHaveTextContent(/^Two\.pdf: Can't reach the LexFlow server/);
  });

  it('reports each removal separately when two are in flight at once', async () => {
    let calls = 0;
    server.use(
      http.delete('*/api/documents/:id', async () => {
        calls += 1;
        if (calls === 1) {
          await delay(150);
          return problem(500, 'internal-error', 'Disk unavailable.');
        }
        return undefined; // the second removal goes to the normal fake API
      }),
    );
    const { user } = await openDocuments();
    const first = 'Cease and Desist Notice.pdf';
    const second = 'Plaint with Interim Application.pdf';

    await user.click(screen.getByRole('button', { name: `Remove ${first}` }));
    await user.click(screen.getByRole('button', { name: `Remove ${second}` }));

    const live = screen.getByRole('list', { name: 'Case documents' });
    await waitFor(() => expect(within(live).queryByText(second)).not.toBeInTheDocument());
    expect(await screen.findByRole('alert')).toHaveTextContent(
      `${first} was not removed. Disk unavailable.`,
    );
    // The failed one can be tried again; it isn't stuck as "Removing".
    expect(screen.getByRole('button', { name: `Remove ${first}` })).toBeEnabled();
  });

  it('treats a document already removed elsewhere as removed', async () => {
    server.use(
      http.delete('*/api/documents/:id', ({ params }) => {
        // Another tab removed it first.
        const owner = mockApiState().cases.find((c) => c.id === 'case-1005');
        if (owner) owner.documents = owner.documents.filter((d) => d.id !== params.id);
        return problem(404, 'document-not-found', 'No document with this id exists.');
      }),
    );
    const { user } = await openDocuments();

    await user.click(screen.getByRole('button', { name: 'Remove Cease and Desist Notice.pdf' }));

    await waitFor(() =>
      expect(screen.queryByText('Cease and Desist Notice.pdf')).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('keeps upload progress and results when the user switches tabs', async () => {
    server.use(
      http.post('*/api/cases/:id/documents', async () => {
        await delay(100);
        return undefined; // then the normal fake API stores the file
      }),
    );
    const { user } = await openDocuments();

    await user.upload(picker(), [pdf('One.pdf'), pdf('Two.pdf')]);
    expect(await screen.findByText(/Uploading One\.pdf/)).toBeInTheDocument();
    await user.click(tab(/Overview/));
    await user.click(tab(/Documents/));

    expect(await screen.findByText('Added 2 documents.')).toBeInTheDocument();
    expect(mockApiState().files.size).toBe(2);
  });

  it('says so when files are dropped while an upload is running', async () => {
    server.use(
      http.post('*/api/cases/:id/documents', async () => {
        await delay(150);
        return undefined;
      }),
    );
    const { user } = await openDocuments();

    await user.upload(picker(), pdf('First.pdf'));
    expect(await screen.findByText(/Uploading First\.pdf/)).toBeInTheDocument();
    const zone = screen.getByTestId('document-drop-zone');
    const dataTransfer = { files: [pdf('Late.pdf')], dropEffect: 'copy' };
    fireEvent.dragOver(zone, { dataTransfer });
    // A real browser only fires `drop` if dragover left dropEffect other than
    // 'none' (jsdom doesn't enforce this, so check it here).
    expect(dataTransfer.dropEffect).not.toBe('none');
    fireEvent.drop(zone, { dataTransfer });

    expect(
      screen.getByText(
        'Late.pdf not added: wait for the current upload to finish, then add again.',
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText('Added First.pdf.')).toBeInTheDocument();
    expect(mockApiState().files.size).toBe(1);
  });
});
