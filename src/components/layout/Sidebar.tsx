import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  FolderKanban,
  CalendarClock,
  BookOpenText,
  Users,
  ShieldCheck,
  Scale,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  /** Shown only to Administrators. */
  adminOnly?: boolean;
}

// Documents, analysis and research live inside each case's workspace.
const navItems: NavItem[] = [
  { to: '/app/cases', label: 'Cases', icon: FolderKanban },
  { to: '/app/dashboard', label: 'Practice Overview', icon: LayoutDashboard },
  { to: '/app/precedents', label: 'Precedent Library', icon: BookOpenText },
  { to: '/app/hearings', label: 'Hearings', icon: CalendarClock },
  { to: '/app/clients', label: 'Clients', icon: Users },
  { to: '/app/admin', label: 'Administration', icon: ShieldCheck, adminOnly: true },
];

interface SidebarProps {
  open: boolean;
  onNavigate: () => void;
}

export function Sidebar({ open, onNavigate }: SidebarProps) {
  const { user } = useAuth();
  const items = navItems.filter((item) => !item.adminOnly || user?.role === 'Administrator');
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-brand-900/40 lg:hidden"
          onClick={onNavigate}
          aria-hidden
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-white/5 bg-brand-900 text-brand-100 transition-transform duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-5">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-accent-500/15 text-accent-500">
            <Scale className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <div className="leading-tight">
            <p className="font-serif text-lg font-bold text-white">LexFlow</p>
            <p className="text-[11px] uppercase tracking-wider text-brand-300">
              Case &amp; Research
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-white/[0.09] text-white [&>svg]:text-accent-500'
                      : 'text-brand-300 hover:bg-white/[0.05] hover:text-white'
                  }`
                }
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-5 py-4 text-[11px] text-brand-400">
          LexFlow v0.2 · Prototype
        </div>
      </aside>
    </>
  );
}
