import { act, render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  MemoryRouter,
  useLocation,
  useNavigate,
  useRoutes,
  type Location,
  type NavigateFunction,
} from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { CasesProvider } from '../context/CasesContext';
import { currentUser } from '../data/mockData';
import { routes } from '../router';

// Must match STORAGE_KEY in AuthContext.
const AUTH_STORAGE_KEY = 'lexflow.auth';

/*
 * Tests run the real route table through <MemoryRouter> + useRoutes rather
 * than createMemoryRouter. The data router builds fetch Requests with an
 * AbortSignal, and under jsdom that signal (from jsdom) is rejected by Node's
 * Request. LexFlow's routes have no loaders or actions, so both routers
 * resolve, redirect and render these routes the same way.
 */
function AppRoutes() {
  return useRoutes(routes);
}

interface Probe {
  location: Location | null;
  navigate: NavigateFunction | null;
}

function RouterProbe({ probe }: { probe: Probe }) {
  probe.location = useLocation();
  probe.navigate = useNavigate();
  return null;
}

/**
 * Renders the real routes, providers and pages, starting at `path`.
 * `url()` reads the current path and query; `go(n)` moves through history.
 */
export function renderApp(path: string, { signedIn = true }: { signedIn?: boolean } = {}) {
  if (signedIn) localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(currentUser));

  const probe: Probe = { location: null, navigate: null };
  // applyAccept: false lets a test pick a file the `accept` hint would hide,
  // as a user can by switching the dialog to "All files".
  const user = userEvent.setup({ applyAccept: false });

  render(
    <AuthProvider>
      <CasesProvider>
        <MemoryRouter initialEntries={[path]}>
          <RouterProbe probe={probe} />
          <AppRoutes />
        </MemoryRouter>
      </CasesProvider>
    </AuthProvider>,
  );

  return {
    user,
    url: () => (probe.location ? probe.location.pathname + probe.location.search : ''),
    go: (delta: number) =>
      act(() => {
        probe.navigate?.(delta);
      }),
  };
}
