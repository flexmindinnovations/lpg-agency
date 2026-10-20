import type { AuditLogEntryResponse } from '@lpg/shared/data-access';
import { formatEntityName, toSentenceCase } from '@lpg/shared/ui';
import { formatDisplayDateTime } from '@lpg/shared/util';

/** How each audited action reads to an office user. */
export const ACTION_LABELS: Readonly<Record<string, string>> = {
  create: 'Created',
  update: 'Changed',
  delete: 'Deleted',
};

export function actionLabel(action: unknown): string {
  return ACTION_LABELS[String(action)] ?? toSentenceCase(action);
}

/** "Order Status History" for `order_status_history`. */
export function entityTypeLabel(entityName: unknown): string {
  return formatEntityName(entityName);
}

/** The record a row is about, by name or number — never a raw id. */
export function recordLabel(entry: AuditLogEntryResponse): string {
  return entry.entity_display_name || entityTypeLabel(entry.entity_name);
}

export function actorLabel(entry: AuditLogEntryResponse): string {
  if (entry.actor_display_name) return entry.actor_display_name;
  return entry.actor_id ? 'Unknown user' : 'System';
}

/** Bookkeeping columns every table has; they never help explain a change. */
const HIDDEN_FIELDS = new Set([
  'id',
  'tenant_id',
  'created_at',
  'created_by',
  'updated_at',
  'updated_by',
  'deleted_at',
  'deleted_by',
  'is_deleted',
  'version',
  'password_hash',
]);

export interface AuditChange {
  readonly field: string;
  readonly before: string;
  readonly after: string;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  const text = String(value);
  // Timestamps read like every other date in the app.
  if (/^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/.test(text)) {
    return formatDisplayDateTime(text);
  }
  return text;
}

/**
 * The field-by-field view of one entry: for a change, only the fields that
 * changed (before → after); for a create or delete, the record's values.
 */
export function auditChanges(entry: AuditLogEntryResponse): AuditChange[] {
  const before = (entry.before_state ?? {}) as Record<string, unknown>;
  const after = (entry.after_state ?? {}) as Record<string, unknown>;
  const fields =
    entry.action === 'update'
      ? Object.keys(before)
      : Object.keys(entry.action === 'delete' ? before : after);
  return fields
    .filter((field) => !HIDDEN_FIELDS.has(field))
    .map((field) => ({
      field: toSentenceCase(field),
      before: entry.action === 'create' ? '' : displayValue(before[field]),
      after: entry.action === 'delete' ? '' : displayValue(after[field]),
    }));
}

function csvCell(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** The loaded entries as CSV, in the columns the grid shows. */
export function auditLogCsv(entries: readonly AuditLogEntryResponse[]): string {
  const header = ['When', 'Record', 'Record type', 'Action', 'Done by'];
  const rows = entries.map((entry) => [
    formatDisplayDateTime(entry.performed_at),
    recordLabel(entry),
    entityTypeLabel(entry.entity_name),
    actionLabel(entry.action),
    actorLabel(entry),
  ]);
  return [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
}
