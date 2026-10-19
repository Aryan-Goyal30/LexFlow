import type { CasePriority, CaseStatus, PracticeArea } from '../types';
import { todayIsoDate } from './format';

/**
 * What the "Add New Case" form holds while the user edits it. Field names
 * match the API's request fields, so server validation errors (keyed by field)
 * map straight onto the form.
 */
export interface NewCaseForm {
  title: string;
  clientId: string;
  practiceArea: PracticeArea;
  status: CaseStatus;
  priority: CasePriority;
  leadAdvocateId: string;
  courtName: string;
  opposingParty: string;
  nextHearing: string;
  description: string;
}

export type NewCaseErrors = Partial<Record<keyof NewCaseForm, string>>;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Checks the form before sending it, for quick feedback. The server applies
 * the same rules (and has the final say, e.g. "today" in Asia/Kolkata).
 * Returns one message per invalid field; an empty object means valid.
 */
export function validateNewCase(
  form: NewCaseForm,
  clientIds: readonly string[],
  advocateIds: readonly string[],
  today: string = todayIsoDate(),
): NewCaseErrors {
  const errors: NewCaseErrors = {};

  if (form.title.trim().length < 4) {
    errors.title = 'Enter a descriptive case title (at least 4 characters).';
  }
  if (!clientIds.includes(form.clientId)) {
    errors.clientId = 'Select a client from the list.';
  }
  if (!advocateIds.includes(form.leadAdvocateId)) {
    errors.leadAdvocateId = 'Select a lead advocate from the list.';
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
