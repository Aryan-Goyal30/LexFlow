import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { KeyRound, LogOut, Scale } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { ErrorState, LoadingState } from '../ui/QueryState';
import { HOME_PATH, PORTAL_PASSWORD_PATH, PORTAL_PATH } from '../../lib/paths';

/**
 * The client portal's shell. Only Client accounts get in (staff are sent to
 * the app); the server enforces the same split on every route.
 */
export function PortalLayout() {
  const { user, status, error, retry, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (status === 'loading') {
    return (
      <div className="grid min-h-screen place-items-center bg-brand-50">
        <LoadingState label="Checking your session…" />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className="grid min-h-screen place-items-center bg-brand-50">
        <ErrorState title="Couldn't reach LexFlow" error={error} onRetry={retry} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (user.role !== 'Client') return <Navigate to={HOME_PATH} replace />;
  if (user.mustChangePassword && location.pathname !== PORTAL_PASSWORD_PATH) {
    return <Navigate to={PORTAL_PASSWORD_PATH} replace />;
  }

  const signOut = async () => {
    await logout().catch(() => undefined);
    navigate('/', { replace: true });
  };

  return (
    <div className="min-h-screen bg-brand-50">
      <header className="border-b border-brand-100 bg-white">
        <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-4 sm:px-6">
          <Link to={PORTAL_PATH} className="flex items-center gap-2 font-semibold text-brand-900">
            <Scale className="h-5 w-5 text-accent-600" aria-hidden="true" />
            LexFlow <span className="font-normal text-brand-500">Client Portal</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-sm text-brand-700 sm:inline">{user.name}</span>
            <Link
              to={PORTAL_PASSWORD_PATH}
              className="rounded-md p-2 text-brand-500 hover:bg-brand-50"
              aria-label="Change password"
              title="Change password"
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />
            </Link>
            <button
              type="button"
              onClick={() => void signOut()}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-brand-600 hover:bg-brand-50"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
