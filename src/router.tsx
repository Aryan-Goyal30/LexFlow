import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { PortalLayout } from './components/layout/PortalLayout';
import { PortalCasePage, PortalCasesPage } from './pages/portal/PortalPages';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { CasesPage } from './pages/CasesPage';
import { CaseWorkspacePage } from './pages/CaseWorkspacePage';
import { NewCasePage } from './pages/NewCasePage';
import { EditCasePage } from './pages/EditCasePage';
import { DocumentTextPage } from './pages/DocumentTextPage';
import { ClientsPage } from './pages/ClientsPage';
import { HearingsPage } from './pages/HearingsPage';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { AdminAuditPage } from './pages/admin/AdminAuditPage';
import { ClientPage, NewClientPage } from './pages/ClientPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { HOME_PATH } from './lib/paths';

/** The route table, exported so tests can run it in a memory router. */
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <LoginPage />,
  },
  {
    path: '/app',
    element: <AppLayout />,
    children: [
      // Cases are the home of the product; the practice overview is secondary.
      { index: true, element: <Navigate to={HOME_PATH} replace /> },
      { path: 'cases', element: <CasesPage /> },
      { path: 'cases/new', element: <NewCasePage /> },
      { path: 'cases/:caseId', element: <CaseWorkspacePage /> },
      { path: 'cases/:caseId/edit', element: <EditCasePage /> },
      { path: 'cases/:caseId/documents/:documentId/text', element: <DocumentTextPage /> },
      { path: 'hearings', element: <HearingsPage /> },
      { path: 'admin', element: <Navigate to="/app/admin/users" replace /> },
      { path: 'admin/users', element: <AdminUsersPage /> },
      { path: 'admin/audit', element: <AdminAuditPage /> },
      { path: 'clients', element: <ClientsPage /> },
      { path: 'clients/new', element: <NewClientPage /> },
      { path: 'clients/:clientId', element: <ClientPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'account/password', element: <ChangePasswordPage /> },
    ],
  },
  {
    // The client portal: Client accounts only.
    path: '/portal',
    element: <PortalLayout />,
    children: [
      { index: true, element: <PortalCasesPage /> },
      { path: 'cases/:caseId', element: <PortalCasePage /> },
      { path: 'account/password', element: <ChangePasswordPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];

export const router = createBrowserRouter(routes);
