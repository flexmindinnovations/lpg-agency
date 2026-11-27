import { toSentenceCase } from '../status-chip-cell/status-chip-cell';

/**
 * The facts that tell two customers apart in a picker: phone, consumer number,
 * and the connection status when it is not active. Every customer picker uses
 * this, so they read the same.
 */
export function customerFacts(customer: {
  phone_number: string;
  consumer_number?: string | null;
  status: string;
}): string {
  return [
    customer.phone_number,
    customer.consumer_number,
    customer.status === 'active' ? null : toSentenceCase(customer.status),
  ]
    .filter(Boolean)
    .join(' · ');
}
