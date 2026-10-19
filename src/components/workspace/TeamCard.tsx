import { useId, useState, type FormEvent } from 'react';
import { Loader2, UserMinus, UserPlus } from 'lucide-react';
import type { Case } from '../../types';
import { useAddTeamMember, useRemoveTeamMember, useStaff } from '../../hooks/useCases';
import { ApiError, errorMessage } from '../../services/api/client';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';

const MEMBER_ROLE_LABELS = { associate: 'Associate advocate', paralegal: 'Paralegal' } as const;

/**
 * Who works on the case. The Administrator and the lead advocate may add
 * Advocates and Paralegals to the team or take them off it; team members gain
 * (or lose) access to the case straight away.
 */
export function TeamCard({ legalCase: c }: { legalCase: Case }) {
  const manage = c.permissions.canManageTeam;
  return (
    <Card>
      <CardHeader title="Case Team" />
      <CardBody className="space-y-4">
        <ul className="space-y-2" aria-label="Case team">
          <li className="flex items-center justify-between gap-2">
            <div>
              <p className="text-sm text-brand-800">{c.leadAttorney}</p>
              <p className="text-xs text-brand-400">Lead advocate</p>
            </div>
          </li>
          {c.team.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm text-brand-800">{member.name}</p>
                <p className="text-xs text-brand-400">{MEMBER_ROLE_LABELS[member.memberRole]}</p>
              </div>
              {manage && <RemoveButton caseId={c.id} userId={member.id} name={member.name} />}
            </li>
          ))}
        </ul>
        {c.team.length === 0 && (
          <p className="text-sm text-brand-500">No one else is on the team yet.</p>
        )}
        {manage && <AddMember legalCase={c} />}
      </CardBody>
    </Card>
  );
}

function RemoveButton({ caseId, userId, name }: { caseId: string; userId: string; name: string }) {
  const remove = useRemoveTeamMember(caseId);
  return (
    <div className="text-right">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => remove.mutate(userId)}
        disabled={remove.isPending}
        aria-label={`Remove ${name} from the case team`}
      >
        {remove.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <UserMinus className="h-4 w-4" aria-hidden="true" />
        )}
      </Button>
      {remove.isError && (
        <p role="alert" className="text-xs text-red-600">
          {name} was not removed. {errorMessage(remove.error)}
        </p>
      )}
    </div>
  );
}

function AddMember({ legalCase: c }: { legalCase: Case }) {
  const staff = useStaff();
  const add = useAddTeamMember(c.id);
  const [userId, setUserId] = useState('');
  const selectId = useId();
  const errorId = useId();

  const onTeam = new Set([c.leadAdvocateId, ...c.team.map((m) => m.id)]);
  const candidates = (staff.data ?? []).filter((s) => !onTeam.has(s.id));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!userId || add.isPending) return;
    add.mutate(userId, { onSuccess: () => setUserId('') });
  };

  if (staff.isPending) return <p className="text-sm text-brand-500">Loading colleagues…</p>;
  if (staff.isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        Couldn't load the list of colleagues. {errorMessage(staff.error)}
      </p>
    );
  }
  if (candidates.length === 0) {
    return <p className="text-sm text-brand-500">Every advocate and paralegal is on this case.</p>;
  }

  const problem =
    add.error instanceof ApiError
      ? (add.error.fieldErrors.userId ?? errorMessage(add.error))
      : add.error
        ? errorMessage(add.error)
        : null;

  return (
    <form onSubmit={submit} className="border-t border-brand-100 pt-4" aria-label="Add to team">
      <label htmlFor={selectId} className="label-text">
        Add to the team
      </label>
      <div className="flex gap-2">
        <select
          id={selectId}
          className="input-field"
          value={userId}
          onChange={(e) => {
            setUserId(e.target.value);
            add.reset();
          }}
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? errorId : undefined}
        >
          <option value="">Choose a colleague…</option>
          {candidates.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.role === 'Advocate' ? 'advocate' : 'paralegal'})
            </option>
          ))}
        </select>
        <Button type="submit" size="sm" disabled={!userId || add.isPending}>
          {add.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <UserPlus className="h-4 w-4" aria-hidden="true" />
          )}
          Add
        </Button>
      </div>
      {problem && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-red-600">
          {problem}
        </p>
      )}
    </form>
  );
}
