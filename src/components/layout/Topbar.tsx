import { Link, useNavigate } from 'react-router-dom';
import { Menu, LogOut, Search, Bell, KeyRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { initials } from '../../lib/format';
import { CHANGE_PASSWORD_PATH } from '../../lib/paths';

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    // Ends the session on the server; the local cache is cleared either way.
    await logout().catch(() => undefined);
    navigate('/', { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-brand-100 bg-white/90 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md p-2 text-brand-600 hover:bg-brand-50 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="relative hidden max-w-md flex-1 sm:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400" />
        <input
          type="text"
          placeholder="Search cases, clients, documents…"
          className="w-full rounded-md border border-brand-200 bg-brand-50/60 py-2 pl-9 pr-3 text-sm placeholder:text-brand-400 focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-500/20"
          disabled
        />
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          className="rounded-md p-2 text-brand-500 hover:bg-brand-50"
          aria-label="Notifications"
          disabled
        >
          <Bell className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-2.5 border-l border-brand-100 pl-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-800 text-sm font-semibold text-white">
            {user ? initials(user.name) : '—'}
          </span>
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-semibold text-brand-900">{user?.name}</p>
            <p className="text-xs text-brand-500">{user?.role}</p>
          </div>
          <Link
            to={CHANGE_PASSWORD_PATH}
            className="rounded-md p-2 text-brand-500 hover:bg-brand-50 hover:text-brand-800"
            aria-label="Change password"
            title="Change password"
          >
            <KeyRound className="h-[18px] w-[18px]" />
          </Link>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="rounded-md p-2 text-brand-500 hover:bg-brand-50 hover:text-brand-800"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="h-[18px] w-[18px]" />
          </button>
        </div>
      </div>
    </header>
  );
}
