import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderApp } from '../test/renderApp';

// A sample case with documents, court and opposing party.
const CASE_URL = '/app/cases/case-1005';

const tab = (name: RegExp) => screen.getByRole('tab', { name });

describe('Workspace tabs and the URL', () => {
  it('puts the selected tab in the query string', async () => {
    const { url, user } = renderApp(CASE_URL);

    expect(tab(/Overview/)).toHaveAttribute('aria-selected', 'true');
    await user.click(tab(/Documents/));
    expect(url()).toBe(`${CASE_URL}?tab=documents`);
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName(/Documents/);

    await user.click(tab(/Overview/));
    expect(url()).toBe(CASE_URL);
  });

  it('lets Back and Forward step through tabs without duplicate entries', async () => {
    const { url, user, go } = renderApp(CASE_URL);

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

  it('opens a tab directly from the URL', () => {
    renderApp(`${CASE_URL}?tab=research`);
    expect(tab(/Research/)).toHaveAttribute('aria-selected', 'true');
  });

  it('shows Overview for an unknown tab and removes it from the URL', async () => {
    const { url } = renderApp(`${CASE_URL}?tab=bogus`);
    expect(tab(/Overview/)).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => expect(url()).toBe(CASE_URL));
  });

  it('moves focus between tabs with the arrow keys without selecting them', async () => {
    const { url, user } = renderApp(CASE_URL);

    tab(/Overview/).focus();
    await user.keyboard('{ArrowRight}');
    expect(tab(/Documents/)).toHaveFocus();
    expect(url()).toBe(CASE_URL);

    await user.keyboard('{End}');
    expect(tab(/Research/)).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(url()).toBe(`${CASE_URL}?tab=research`);
  });

  it('explains that a missing case may have been lost on refresh', () => {
    renderApp('/app/cases/case-from-an-earlier-session');
    expect(screen.getByRole('heading', { name: 'Case not found' })).toBeInTheDocument();
    expect(screen.getByText(/kept in memory only/)).toBeInTheDocument();
  });
});

describe('AI Analysis and Research while no service is connected', () => {
  it('marks both tabs as not connected', () => {
    renderApp(CASE_URL);
    expect(tab(/AI Analysis/)).toHaveTextContent('Not connected');
    expect(tab(/Research/)).toHaveTextContent('Not connected');
  });

  it('shows the unavailable state on AI Analysis and no results', () => {
    renderApp(`${CASE_URL}?tab=analysis`);

    expect(screen.getByText('AI analysis is not connected yet')).toBeInTheDocument();
    const analyse = screen.getByRole('button', { name: /Analyse case/ });
    expect(analyse).toBeDisabled();
    expect(analyse).toHaveAccessibleDescription(/no AI service is connected/);
    expect(screen.getAllByText('Not connected').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Relevant Precedents/)).not.toBeInTheDocument();
    // The inputs panel is real case data.
    expect(screen.getByText('4 on file, 0 uploaded this session')).toBeInTheDocument();
  });

  it('shows the unavailable state on Research and no results', () => {
    renderApp(`${CASE_URL}?tab=research`);

    expect(screen.getByText('Precedent research is not connected yet')).toBeInTheDocument();
    expect(screen.getByRole('searchbox', { name: 'Search precedents' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Search precedents' })).toBeDisabled();
    expect(screen.queryByText(/Results for/)).not.toBeInTheDocument();
    expect(
      screen.getByText('Precedent search becomes available once research is connected.'),
    ).toBeInTheDocument();
  });
});

describe('Documents tab', () => {
  const pdf = (name = 'Rejoinder.pdf') =>
    new File(['%PDF-1.4 test'], name, { type: 'application/pdf' });

  const openDocuments = () => renderApp(`${CASE_URL}?tab=documents`);

  it('adds a supported file chosen with the picker', async () => {
    const { user } = await openDocuments();

    await user.upload(screen.getByLabelText('Choose files to attach'), pdf());

    expect(screen.getByRole('status')).toHaveTextContent('Added Rejoinder.pdf.');
    expect(screen.getByRole('link', { name: 'Open Rejoinder.pdf' })).toHaveAttribute(
      'href',
      expect.stringMatching(/^blob:/),
    );
    expect(tab(/Documents/)).toHaveTextContent('5');
  });

  it('rejects unsupported files from the picker with a reason', async () => {
    const { user } = await openDocuments();

    await user.upload(screen.getByLabelText('Choose files to attach'), [
      new File(['MZ'], 'setup.exe'),
      new File([''], 'Empty.pdf'),
    ]);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('2 files were not added');
    expect(status).toHaveTextContent('setup.exe is not a supported file type');
    expect(status).toHaveTextContent('Empty.pdf is empty');
    expect(screen.queryByText('setup.exe', { selector: 'p' })).not.toBeInTheDocument();
    expect(tab(/Documents/)).toHaveTextContent('4');
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

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Added Notes.txt.');
    expect(status).toHaveTextContent('setup.exe is not a supported file type');
    expect(status).toHaveTextContent('Cease and Desist Notice.pdf is already attached');
    expect(tab(/Documents/)).toHaveTextContent('5');
  });

  it('ignores an empty selection', async () => {
    await openDocuments();
    fireEvent.change(screen.getByLabelText('Choose files to attach'), {
      target: { files: [] },
    });
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('revokes the object URL when an uploaded document is removed', async () => {
    const revoke = vi.spyOn(URL, 'revokeObjectURL');
    const { user } = await openDocuments();

    await user.upload(screen.getByLabelText('Choose files to attach'), pdf());
    const href = screen.getByRole('link', { name: 'Open Rejoinder.pdf' }).getAttribute('href');
    await user.click(screen.getByRole('button', { name: 'Remove Rejoinder.pdf' }));

    expect(revoke).toHaveBeenCalledWith(href);
    expect(screen.queryByRole('link', { name: 'Open Rejoinder.pdf' })).not.toBeInTheDocument();
  });

  it('labels sample documents that have no file behind them', async () => {
    await openDocuments();
    const item = screen.getByText('Cease and Desist Notice.pdf').closest('li');
    expect(item).not.toBeNull();
    expect(within(item as HTMLElement).getByText(/sample record, no file attached/)).toBeVisible();
  });
});
