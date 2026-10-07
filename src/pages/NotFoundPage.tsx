import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center bg-brand-50 px-6">
      <div className="text-center">
        <p className="font-serif text-6xl font-bold text-brand-900">404</p>
        <p className="mt-3 text-sm text-brand-500">
          The page you're looking for doesn't exist.
        </p>
        <Link to="/app/dashboard" className="mt-6 inline-block">
          <Button>Go to Dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
