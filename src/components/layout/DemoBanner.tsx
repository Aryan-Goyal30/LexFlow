import { FlaskConical, ShieldAlert } from 'lucide-react';
import { useDemoStatus } from '../../hooks/useDemo';

/**
 * Shown on every staff page while the server runs in demo mode. In the
 * verified demo database everything is fictional; if demo mode is on but the
 * database could not be verified, fictional records are refused and the
 * banner says so. Nothing is shown when demo mode is off.
 */
export function DemoBanner() {
  const demo = useDemoStatus();
  if (!demo.data?.enabled) return null;
  if (demo.data.verified) {
    return (
      <aside
        aria-label="Demo environment"
        className="flex items-start gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900 sm:px-6 lg:px-8"
      >
        <FlaskConical className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          <strong>Demo environment.</strong> Every client, case, document and judgment here is
          fictional, and AI output comes from a scripted test provider (not AI). Nothing here is a
          real legal record or legal advice.
        </span>
      </aside>
    );
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-2 border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800 sm:px-6 lg:px-8"
    >
      <ShieldAlert className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{demo.data.reason}</span>
    </div>
  );
}
