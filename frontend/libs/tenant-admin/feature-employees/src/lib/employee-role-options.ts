/** Matches `identity.role` (`VALID_ROLES`, `domain/identity/user.py`) minus
 * `super_admin` (platform-level, not assignable from tenant admin) and
 * `customer` (registered via the Customer onboarding flow, not this form).
 * Shared between the register and edit forms so they can't drift apart. */
export const ROLE_OPTIONS: { label: string; value: string }[] = [
  { label: 'Agency Admin', value: 'agency_admin' },
  { label: 'Manager', value: 'manager' },
  { label: 'Dispatcher', value: 'dispatcher' },
  { label: 'Warehouse Staff', value: 'warehouse_staff' },
  { label: 'Accountant', value: 'accountant' },
  { label: 'Driver', value: 'driver' },
];
