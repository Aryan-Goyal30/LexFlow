import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderKanban,
  CalendarClock,
  BookOpenText,
  Users,
  Bell,
  ShieldCheck,
  Scale,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  enabled: boolean;
}

// Documents, analysis and research live inside each case's workspace. The
// "Soon" items are firm-wide views planned for later milestones.
const navItems: NavItem[] = [
  { to: '/app/cases', label: 'Cases', icon: FolderKanban, enabled: true },
  { to: '/app/dashboard', label: 'Overview', icon: LayoutDashboard, enabled: true },
  { to: '/app/research', label: 'Precedent Library', icon: BookOpenText, enabled: false },
  { to: '/app/hearings', label: 'Hearings', icon: CalendarClock, enabled: false },
  { to: '/app/clients', label: 'Clients', icon: Users, enabled: false },
  { to: '/app/notifications', label: 'Notifications', icon: Bell, enabled: false },
  { to: '/app/admin', label: 'Administration', icon: ShieldCheck, enabled: false },
];

interface SidebarProps {
  open: boolean;
  onNavigate: () => void;
}

export function Sidebar({ open, onNavigate }: SidebarProps) {
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
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-brand-900 text-brand-100 transition-transform duration-200 lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-5">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-accent-500/15 text-accent-500">
            <Scale className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <div className="leading-tight">
            <p className="font-serif text-lg font-bold text-white">LexFlow</p>
            <p className="text-[11px] uppercase tracking-wider text-brand-300">Case &amp; Research</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            if (!item.enabled) {
              return (
                <div
                  key={item.to}
                  className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-brand-400/70"
                  title="Coming in a later milestone"
                >
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                  <span>{item.label}</span>
                  <span className="ml-auto text-[10px] uppercase tracking-wide text-brand-500">
                    Soon
                  </span>
                </div>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-white/10 text-white'
                      : 'text-brand-200 hover:bg-white/5 hover:text-white'
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
