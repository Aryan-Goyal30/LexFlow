import { Link, useNavigate } from 'react-router-dom';
import { Menu, LogOut, KeyRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { initials } from '../../lib/format';
import { CHANGE_PASSWORD_PATH } from '../../lib/paths';
import { GlobalSearch } from './GlobalSearch';

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
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-brand-100 bg-white px-4 sm:px-6 lg:px-10">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md p-2 text-brand-600 hover:bg-brand-50 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      <GlobalSearch />

      <div className="ml-auto flex items-center">
        <div className="flex items-center gap-2.5">
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
