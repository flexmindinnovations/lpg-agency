/**
 * Human-readable names for the fixed role catalog (`VALID_ROLES`,
 * `backend/src/lpg/domain/identity/user.py`). Screens showed raw codes such as
 * "Agency_admin" (QA finding DA-30); every place that shows a role to a person
 * uses this instead.
 */
export const ROLE_LABELS: Readonly<Record<string, string>> = {
  super_admin: 'Super Admin',
  agency_admin: 'Agency Admin',
  manager: 'Manager',
  warehouse_staff: 'Godown Staff',
  dispatcher: 'Dispatcher',
  accountant: 'Accountant',
  driver: 'Driver',
  customer: 'Customer',
};

/** The display name of a role code; unknown codes are sentence-cased. */
export function roleLabel(role: string | null | undefined): string {
  if (!role) return '';
  const known = ROLE_LABELS[role];
  if (known) return known;
  const words = role.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Roles an agency admin can give a Dashboard staff account (mirrors
 * `ASSIGNABLE_STAFF_ROLES`, `application/identity/staff_user.py`). */
export const ASSIGNABLE_STAFF_ROLES: readonly string[] = [
  'agency_admin',
  'manager',
  'warehouse_staff',
  'dispatcher',
  'accountant',
];
