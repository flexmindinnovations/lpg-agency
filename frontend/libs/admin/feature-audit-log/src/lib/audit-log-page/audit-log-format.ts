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
export const HIDDEN_FIELDS = new Set([
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

export interface TechnicalIdentifier {
  readonly key: string;
  readonly label: string;
  readonly value: string;
  readonly isOrderId?: boolean;
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
  // Slugs, enum codes and lowercase statuses format in Sentence case.
  if (/^[a-z][a-z0-9_-]*$/.test(text)) {
    return toSentenceCase(text);
  }
  return text;
}

export function isTechnicalIdField(field: string): boolean {
  return (
    HIDDEN_FIELDS.has(field) ||
    field.endsWith('_id') ||
    field.endsWith('Id') ||
    field === 'changed_by' ||
    field === 'created_by' ||
    field === 'updated_by' ||
    field === 'deleted_by'
  );
}

function formatIdentifierLabel(key: string): string {
  const customLabels: Record<string, string> = {
    record_id: 'Record ID',
    user_id: 'User ID',
    correlation_id: 'Correlation ID',
    log_id: 'Log ID',
    order_id: 'Order ID',
    route_id: 'Route ID',
    customer_id: 'Customer ID',
    vehicle_id: 'Vehicle ID',
    driver_id: 'Driver ID',
    changed_by: 'Changed By (User ID)',
  };
  if (customLabels[key]) return customLabels[key];
  if (key.endsWith('_id')) {
    return `${toSentenceCase(key.slice(0, -3))} ID`;
  }
  return toSentenceCase(key);
}

/**
 * Extracts all technical identifiers from the audit entry and its states.
 */
export function technicalIdentifiersOf(entry: AuditLogEntryResponse): TechnicalIdentifier[] {
  const map = new Map<string, string>();

  if (entry.entity_id) map.set('record_id', entry.entity_id);
  if (entry.actor_id) map.set('user_id', entry.actor_id);
  if (entry.correlation_id) map.set('correlation_id', entry.correlation_id);
  if (entry.id) map.set('log_id', entry.id);

  const state = {
    ...((entry.before_state as Record<string, unknown>) ?? {}),
    ...((entry.after_state as Record<string, unknown>) ?? {}),
  };

  for (const [key, val] of Object.entries(state)) {
    if (val === null || val === undefined || val === '') continue;
    const strVal = String(val);
    const isId = key.endsWith('_id') || key.endsWith('Id') || key === 'changed_by';
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(strVal);

    if ((isId || isUuid) && !map.has(key)) {
      map.set(key, strVal);
    }
  }

  const isEntryOrder =
    entry.entity_name === 'orders' ||
    entry.entity_name === 'order' ||
    (entry.entity_display_name?.startsWith('ORD') ?? false);

  return Array.from(map.entries()).map(([key, value]) => ({
    key,
    label: formatIdentifierLabel(key),
    value,
    isOrderId: key === 'order_id' || (key === 'record_id' && isEntryOrder),
  }));
}

/**
 * Resolves an order ID for navigation if the entry is an order or references one.
 */
export function orderIdForEntry(entry: AuditLogEntryResponse): string | null {
  const state = {
    ...((entry.before_state as Record<string, unknown>) ?? {}),
    ...((entry.after_state as Record<string, unknown>) ?? {}),
  };

  if (state['order_id']) {
    return String(state['order_id']);
  }

  const isEntryOrder =
    entry.entity_name === 'orders' ||
    entry.entity_name === 'order' ||
    (entry.entity_display_name?.startsWith('ORD') ?? false);

  if (isEntryOrder && entry.entity_id) {
    return entry.entity_id;
  }

  return null;
}

/**
 * The field-by-field view of one entry: for a change, only the fields that
 * changed (before → after); for a create or delete, the record's values.
 * Technical identifiers are excluded from this table and shown in Technical Identifiers.
 */
export function auditChanges(entry: AuditLogEntryResponse): AuditChange[] {
  const before = (entry.before_state ?? {}) as Record<string, unknown>;
  const after = (entry.after_state ?? {}) as Record<string, unknown>;
  const fields =
    entry.action === 'update'
      ? Object.keys(before)
      : Object.keys(entry.action === 'delete' ? before : after);
  return fields
    .filter((field) => !isTechnicalIdField(field))
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
