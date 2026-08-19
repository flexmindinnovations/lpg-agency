import { Component, signal } from '@angular/core';
import { Tag } from 'primeng/tag';

export type ChipSeverity = 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast';

/**
 * Converts a raw enum/status value into Sentence case for display —
 * `"pending_approval"` → `"Pending approval"`, `"out-for-delivery"` →
 * `"Out for delivery"`, `"active"` → `"Active"`, and also splits
 * camelCase/PascalCase word boundaries (`"InProgress"` → `"In progress"`) —
 * some enums (`ComplaintStatus`) are serialized that way rather than
 * snake_case, with no separator character to split on otherwise.
 */
export function toSentenceCase(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  const normalized = String(value)
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]/g, ' ')
    .trim();
  if (!normalized) return '—';
  return normalized.charAt(0).toUpperCase() + normalized.slice(1).toLowerCase();
}

/**
 * Best-effort fallback severity for a column with no explicit `severityMap`.
 * Prefer passing a column-specific map — the same word means opposite things
 * in different domains ("closed" is a good outcome for a complaint, a
 * neutral-to-bad one for a customer account) — this only covers the common
 * case where the default reads correctly regardless of context.
 */
const DEFAULT_SEVERITY_BY_VALUE: Record<string, ChipSeverity> = {
  active: 'success',
  verified: 'success',
  approved: 'success',
  resolved: 'success',
  delivered: 'success',
  completed: 'success',
  paid: 'success',
  filled: 'success',
  confirmed: 'success',
  pending: 'warn',
  onboarding: 'warn',
  quarantine: 'warn',
  repair: 'warn',
  in_progress: 'warn',
  out_for_delivery: 'warn',
  assigned: 'info',
  booked: 'info',
  ready_for_dispatch: 'info',
  inactive: 'secondary',
  closed: 'secondary',
  empty: 'secondary',
  scrap: 'secondary',
  rejected: 'danger',
  blocked: 'danger',
  cancelled: 'danger',
  damaged: 'danger',
  leakage: 'danger',
  failed: 'danger',
  expired: 'danger',
};

/**
 * AG Grid cell renderer for any short enum/status column: Sentence-cased
 * text in a coloured `p-tag` chip, in place of a raw lowercase string.
 *
 * Pass a per-column `severityMap` (raw lowercase value → `ChipSeverity`) via
 * `DataGridColumn.cellRendererParams` when the default word-based mapping
 * would read wrong for that column's vocabulary; otherwise the default
 * applies.
 */
@Component({
  selector: 'lpg-status-chip-cell',
  standalone: true,
  imports: [Tag],
  template: `<p-tag [severity]="severity()" [value]="label()" />`,
  styles: [
    `
      :host {
        display: inline-flex;
        vertical-align: middle;
      }
    `,
  ],
})
export class StatusChipCell {
  protected readonly label = signal('');
  protected readonly severity = signal<ChipSeverity>('secondary');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const raw = params.value;
    this.label.set(toSentenceCase(raw));
    const map: Record<string, ChipSeverity> | undefined = params.severityMap;
    const key = typeof raw === 'string' ? raw.toLowerCase() : '';
    this.severity.set(map?.[key] ?? DEFAULT_SEVERITY_BY_VALUE[key] ?? 'secondary');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}
