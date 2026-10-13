import { ButtonLink } from '../components/ui/Button';
import { HOME_PATH } from '../lib/paths';

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-brand-50 px-6">
      <div className="text-center">
        <p className="font-serif text-6xl font-bold text-brand-900">404</p>
        <h1 className="mt-3 text-lg font-semibold text-brand-900">Page not found</h1>
        <p className="mt-1 text-sm text-brand-500">
          This address doesn't match any page in LexFlow. Check the link, or go back to your cases.
        </p>
        <ButtonLink to={HOME_PATH} className="mt-6">
          Go to cases
        </ButtonLink>
      </div>
    </main>
  );
}
