import type { Client } from '../types';

/** What the client form edits. */
export type ClientField = 'name' | 'company' | 'email' | 'phone';
export type ClientFormValues = Record<ClientField, string>;

export const EMPTY_CLIENT: ClientFormValues = { name: '', company: '', email: '', phone: '' };

export function valuesOf(client: Client): ClientFormValues {
  return {
    name: client.name,
    company: client.company ?? '',
    email: client.email,
    phone: client.phone,
  };
}
