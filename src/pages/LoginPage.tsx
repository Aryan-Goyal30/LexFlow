import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Scale, ShieldCheck, FolderKanban, CalendarClock, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/Button';

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('aryan.goyal@lexflow.in');
  const [password, setPassword] = useState('demo1234');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/app/dashboard" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password.trim()) {
      setError('Enter your email and password to continue.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/app/dashboard', { replace: true });
    } catch {
      setError('Unable to sign in. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-between bg-brand-900 p-12 text-brand-100 lg:flex">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-lg bg-accent-500/15 text-accent-500">
            <Scale className="h-6 w-6" strokeWidth={1.75} />
          </span>
          <div>
            <p className="font-serif text-2xl font-bold text-white">LexFlow</p>
            <p className="text-xs uppercase tracking-wider text-brand-300">Legal Case Management</p>
          </div>
        </div>

        <div className="max-w-md">
          <h2 className="font-serif text-3xl font-bold leading-snug text-white">
            Every matter, deadline, and document — organised in one place.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-brand-300">
            LexFlow gives your chamber a single, structured view of active
            matters, hearings, clients, and filings.
          </p>

          <ul className="mt-8 space-y-3 text-sm">
            <li className="flex items-center gap-3">
              <FolderKanban className="h-4 w-4 text-accent-500" />
              Structured case files with status &amp; priority tracking
            </li>
            <li className="flex items-center gap-3">
              <CalendarClock className="h-4 w-4 text-accent-500" />
              Hearing schedules and matter timelines
            </li>
            <li className="flex items-center gap-3">
              <ShieldCheck className="h-4 w-4 text-accent-500" />
              Role-based access for advocates, paralegals &amp; clients
            </li>
          </ul>
        </div>

        <p className="text-xs text-brand-400">
          © {new Date().getFullYear()} LexFlow · Academic prototype (v0.1)
        </p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-900 text-accent-500">
                <Scale className="h-5 w-5" strokeWidth={1.75} />
              </span>
              <p className="font-serif text-xl font-bold text-brand-900">LexFlow</p>
            </div>
          </div>

          <h1 className="text-2xl font-bold text-brand-900">Sign in</h1>
          <p className="mt-1 text-sm text-brand-500">
            Access your case workspace. Use the pre-filled demo credentials or any
            email and password.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="label-text">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="password" className="label-text">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-brand-400">
            Authentication is mocked in v0.1 — no real credentials are stored.
          </p>
        </div>
      </div>
    </div>
  );
}
