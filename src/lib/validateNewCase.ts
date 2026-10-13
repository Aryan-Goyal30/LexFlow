import type { CasePriority, CaseStatus, Client, PracticeArea } from '../types';
import { todayIsoDate } from './format';

/** What the "Add New Case" form holds while the user edits it. */
export interface NewCaseForm {
  title: string;
  clientId: string;
  practiceArea: PracticeArea;
  status: CaseStatus;
  priority: CasePriority;
  leadAttorney: string;
  courtName: string;
  opposingParty: string;
  nextHearing: string;
  description: string;
}

export type NewCaseErrors = Partial<Record<keyof NewCaseForm, string>>;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Returns one message per invalid field; an empty object means valid. */
export function validateNewCase(
  form: NewCaseForm,
  clients: readonly Client[],
  advocates: readonly string[],
  today: string = todayIsoDate(),
): NewCaseErrors {
  const errors: NewCaseErrors = {};

  if (form.title.trim().length < 4) {
    errors.title = 'Enter a descriptive case title (at least 4 characters).';
  }
  if (!clients.some((client) => client.id === form.clientId)) {
    errors.clientId = 'Select a client from the list.';
  }
  if (!advocates.includes(form.leadAttorney)) {
    errors.leadAttorney = 'Select a lead advocate from the list.';
  }
  if (form.description.trim().length < 10) {
    errors.description = 'Provide a short summary (at least 10 characters).';
  }
  if (form.nextHearing) {
    if (!ISO_DATE.test(form.nextHearing)) {
      errors.nextHearing = 'Enter the date as day, month and year.';
    } else if (form.nextHearing < today) {
      errors.nextHearing = 'The next hearing date cannot be in the past.';
    }
  }

  return errors;
}
