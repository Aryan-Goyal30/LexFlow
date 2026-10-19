import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
import { DEFAULT_TEST_USER, mockCurrentUser, mockSignIn } from './mockApi';
import { ME_KEY } from '../context/AuthContext';
import { routes } from '../router';

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
export function renderApp(
  path: string,
  {
    signedIn = true,
    as = DEFAULT_TEST_USER,
    sessionKnown = true,
  }: { signedIn?: boolean; as?: string; sessionKnown?: boolean } = {},
) {
  // A session on the fake server, as if this person had signed in.
  if (signedIn) mockSignIn(as);

  const probe: Probe = { location: null, navigate: null };
  // applyAccept: false lets a test pick a file the `accept` hint would hide,
  // as a user can by switching the dialog to "All files".
  const user = userEvent.setup({ applyAccept: false });

  // A fresh cache per test; no retries, so a failing request shows its error
  // state straight away.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  // Start where the app is once it has asked the server who is signed in, so
  // page tests see the page's own states (`sessionKnown: false` tests the check).
  if (sessionKnown) queryClient.setQueryData(ME_KEY, mockCurrentUser());

  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <RouterProbe probe={probe} />
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  return {
    queryClient,
    user,
    url: () => (probe.location ? probe.location.pathname + probe.location.search : ''),
    go: (delta: number) =>
      act(() => {
        probe.navigate?.(delta);
      }),
  };
}
