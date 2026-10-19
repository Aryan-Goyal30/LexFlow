import { useEffect, useId, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError, errorMessage } from '../services/api/client';
import { Card, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { Field } from '../components/ui/Field';
import { errorId, fieldProps } from '../lib/fields';
import { homeFor } from '../lib/paths';

const MIN_LENGTH = 12;

type Errors = Partial<Record<'currentPassword' | 'newPassword' | 'confirm', string>>;

/**
 * Change your own password. Also the only page a user can reach while an
 * administrator's temporary password is still in use (the server refuses
 * everything else until it is replaced).
 */
export function ChangePasswordPage() {
  const { user, changePassword } = useAuth();
  const navigate = useNavigate();
  const uid = useId();
  const forced = user?.mustChangePassword ?? false;

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  // Set after replacing a temporary password: leave once the new user state has
  // rendered (navigating earlier would meet the old state and be sent back).
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (leaving && user && !user.mustChangePassword) {
      navigate(homeFor(user.role), { replace: true });
    }
  }, [leaving, user, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    const found: Errors = {};
    if (!current) found.currentPassword = 'Enter your current password.';
    if (next.length < MIN_LENGTH) found.newPassword = `Use at least ${MIN_LENGTH} characters.`;
    if (next !== confirm) found.confirm = 'The two new passwords do not match.';
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSaving(true);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      if (forced) {
        setLeaving(true);
      } else {
        setDone(true);
      }
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        setErrors(error.fieldErrors as Errors);
      } else {
        setSaveError(`The password was not changed. ${errorMessage(error)}`);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Change password"
        description="Your other signed-in sessions end when you change it."
      />
      <Card className="max-w-lg">
        <CardBody>
          {forced && (
            <p
              role="status"
              className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20"
            >
              An administrator set a temporary password for you. Choose your own to continue.
            </p>
          )}
          {done && (
            <p
              role="status"
              className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20"
            >
              Your password has been changed.
            </p>
          )}
          <form
            onSubmit={handleSubmit}
            noValidate
            aria-label="Change password"
            className="space-y-4"
          >
            <Field
              label="Current password"
              htmlFor={`${uid}-currentPassword`}
              error={errors.currentPassword}
              errorId={errorId(uid, 'currentPassword')}
              required
            >
              <input
                {...fieldProps(uid, 'currentPassword', errors.currentPassword)}
                type="password"
                autoComplete="current-password"
                className="input-field"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </Field>
            <Field
              label="New password"
              htmlFor={`${uid}-newPassword`}
              error={errors.newPassword}
              errorId={errorId(uid, 'newPassword')}
              hint={`At least ${MIN_LENGTH} characters. A few unrelated words make a strong one.`}
              required
            >
              <input
                {...fieldProps(uid, 'newPassword', errors.newPassword)}
                type="password"
                autoComplete="new-password"
                className="input-field"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </Field>
            <Field
              label="Repeat the new password"
              htmlFor={`${uid}-confirm`}
              error={errors.confirm}
              errorId={errorId(uid, 'confirm')}
              required
            >
              <input
                {...fieldProps(uid, 'confirm', errors.confirm)}
                type="password"
                autoComplete="new-password"
                className="input-field"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </Field>

            {saveError && (
              <p
                role="alert"
                className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
              >
                {saveError}
              </p>
            )}

            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <KeyRound className="h-4 w-4" aria-hidden="true" />
              )}
              {saving ? 'Changing password…' : 'Change password'}
            </Button>
          </form>
        </CardBody>
      </Card>
    </>
  );
}
