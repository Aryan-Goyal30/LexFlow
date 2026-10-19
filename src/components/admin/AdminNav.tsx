import { NavLink } from 'react-router-dom';

const LINKS = [
  { to: '/app/admin/users', label: 'Accounts' },
  { to: '/app/admin/audit', label: 'Audit log' },
];

/** Switches between the Administration pages. */
export function AdminNav() {
  return (
    <nav aria-label="Administration" className="mb-5 flex gap-1 border-b border-brand-100">
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) =>
            `-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              isActive
                ? 'border-brand-800 text-brand-900'
                : 'border-transparent text-brand-500 hover:text-brand-800'
            }`
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
