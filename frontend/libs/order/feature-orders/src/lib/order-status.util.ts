import type { AppError } from '@lpg/shared/data-access';

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

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

export function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    case 'RESOURCE_NOT_FOUND':
      // Covers more than "order not found" — e.g. confirm() surfaces a
      // missing price-list entry via this same error code. The backend's
      // `detail` already names the specific resource, so prefer it.
      return isAppError(error) && error.detail ? error.detail : 'That resource could not be found.';
    case 'INVALID_STATE_TRANSITION':
      return 'That action is not valid for the order in its current state.';
    case 'INSUFFICIENT_VEHICLE_STOCK':
      return 'Not enough stock reserved on the vehicle for that quantity.';
    case 'INCOMPLETE_PROOF_OF_DELIVERY':
      return 'Proof of delivery is incomplete or invalid.';
    case 'OTP_MISMATCH':
      return 'The OTP entered is incorrect.';
    case 'OTP_EXPIRED':
      return 'The OTP has expired — depart again to issue a new one.';
    case 'IDEMPOTENCY_KEY_CONFLICT':
      return 'This request was already submitted with different details.';
    default:
      return 'Something went wrong. Please try again.';
  }
}
