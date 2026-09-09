export { errorMessageFor } from '@lpg/shared/data-access';

export const STATUS_SEVERITY: Record<
  string,
  'success' | 'info' | 'warn' | 'danger' | 'secondary'
> = {
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

export function statusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  return STATUS_SEVERITY[status] ?? 'secondary';
}

export function statusLabel(status: string): string {
  return status
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// errorMessageFor is now the canonical version from @lpg/shared/data-access
// (re-exported above) — it already covers every case this file used to
// hand-roll (PERMISSION_DENIED, RESOURCE_NOT_FOUND with detail-preference,
// INVALID_STATE_TRANSITION, INSUFFICIENT_VEHICLE_STOCK,
// INCOMPLETE_PROOF_OF_DELIVERY, OTP_MISMATCH, OTP_EXPIRED,
// IDEMPOTENCY_KEY_CONFLICT).
