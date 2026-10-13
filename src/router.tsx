import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { CasesPage } from './pages/CasesPage';
import { CaseWorkspacePage } from './pages/CaseWorkspacePage';
import { NewCasePage } from './pages/NewCasePage';
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
      { path: 'dashboard', element: <DashboardPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];

export const router = createBrowserRouter(routes);
