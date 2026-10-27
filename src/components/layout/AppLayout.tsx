import { useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { DemoBanner } from './DemoBanner';
import { useAuth } from '../../context/AuthContext';
import { ErrorState, LoadingState } from '../ui/QueryState';
import { CHANGE_PASSWORD_PATH, PORTAL_PATH } from '../../lib/paths';

/**
 * Authenticated application shell: fixed sidebar + top bar, scrollable content
 * region rendered via <Outlet />.
 *
 * It waits for the server to say who is signed in. Without a session it sends
 * the visitor to sign-in, remembering the requested page; a user who still has
 * to replace a temporary password can only reach the change-password page. The
 * server enforces all of this too: the shell only keeps the screens consistent.
 */
export function AppLayout() {
  const { user, status, error, retry } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
  // Client accounts use the portal; the server refuses them every staff route.
  if (user.role === 'Client') return <Navigate to={PORTAL_PATH} replace />;
  if (user.mustChangePassword && location.pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />;
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <DemoBanner />
        <main className="flex-1 px-4 py-8 sm:px-6 lg:px-10">
          <div className="mx-auto max-w-[76rem]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
