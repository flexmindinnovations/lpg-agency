export { errorMessageFor } from '@lpg/shared/data-access';

export const STATUS_SEVERITY: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> =
  {
    draft: 'secondary',
    booked: 'info',
    confirmed: 'info',
    assigned: 'warn',
    ready_for_dispatch: 'warn',
    out_for_delivery: 'warn',
    delivered: 'success',
    failed_delivery: 'danger',
    cancelled: 'danger',
    closed: 'success',
  };

export function statusSeverity(
  status: string,
): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  return STATUS_SEVERITY[status] ?? 'secondary';
}

/**
 * One wording for each status everywhere on the order screens — list chips,
 * filter, detail header and timeline (DO-26).
 */
export const STATUS_LABELS: Readonly<Record<string, string>> = {
  draft: 'Draft',
  booked: 'Booked',
  confirmed: 'Confirmed',
  assigned: 'On a trip',
  ready_for_dispatch: 'Ready for dispatch',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  failed_delivery: 'Delivery failed',
  cancelled: 'Cancelled',
  closed: 'Closed',
};

export function statusLabel(status: string): string {
  const known = STATUS_LABELS[status];
  if (known) return known;
  const words = status.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Why a delivery failed, as staff read it (reason codes from the driver app). */
export const FAILED_DELIVERY_REASON_LABELS: Readonly<Record<string, string>> = {
  customer_unavailable: 'Customer not available',
  wrong_address: 'Wrong address',
  payment_refused: 'Customer refused to pay',
  vehicle_issue: 'Vehicle problem',
  safety_issue: 'Safety issue',
};

/** The local calendar day of `date` as the start of that day in UTC-free ISO
 *  form the API accepts (`YYYY-MM-DDT00:00:00` + local offset). */
export function startOfLocalDayIso(date: Date): string {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return d.toISOString();
}

export function endOfLocalDayIso(date: Date): string {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
  return d.toISOString();
}

/** A chosen delivery day sent to the API: midday local time, so the date
 *  is the same in UTC for any Indian time zone. */
export function deliveryDayIso(date: Date): string {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12).toISOString();
}

/**
 * Date inputs on the order screens show dd/mm/yyyy (DO-08). No shared
 * date-input format exists in `@lpg/shared/ui` yet, so it is kept here.
 */
export const DATE_INPUT_FORMAT = 'dd/mm/yy';
export const DATE_INPUT_PLACEHOLDER = 'dd/mm/yyyy';

// errorMessageFor is now the canonical version from @lpg/shared/data-access
// (re-exported above) — it already covers every case this file used to
// hand-roll (PERMISSION_DENIED, RESOURCE_NOT_FOUND with detail-preference,
// INVALID_STATE_TRANSITION, INSUFFICIENT_VEHICLE_STOCK,
// INCOMPLETE_PROOF_OF_DELIVERY, OTP_MISMATCH, OTP_EXPIRED,
// IDEMPOTENCY_KEY_CONFLICT).
