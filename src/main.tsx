import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthProvider } from './context/AuthContext';
import { CasesProvider } from './context/CasesContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <CasesProvider>
        <RouterProvider router={router} />
      </CasesProvider>
    </AuthProvider>
  </React.StrictMode>,
);
