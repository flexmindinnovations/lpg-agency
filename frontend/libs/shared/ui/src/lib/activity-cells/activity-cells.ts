import { Component, signal } from '@angular/core';
import { ClipboardModule } from '@angular/cdk/clipboard';
import { Tag } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { formatDisplayDateTime } from '@lpg/shared/util';

/** Formats an ISO-8601 timestamp as the app-wide "11 Aug 2026, 17:23" (IST). */
export function formatTimestamp(value: unknown): string {
  if (!value || typeof value !== 'string') return '—';
  return formatDisplayDateTime(value);
}

/** Truncates a UUID to its first segment for display (e.g. "6139110e…"). */
export function shortId(value: unknown): string {
  if (!value || typeof value !== 'string') return '—';
  const parts = value.split('-');
  return parts.length > 1 ? `${parts[0]}…` : value;
}

/** Makes snake_case entity/module names human-readable (e.g. "inventory_balance" → "Inventory Balance"). */
export function formatEntityName(value: unknown): string {
  if (!value || typeof value !== 'string') return '—';
  return value
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export const ACTION_SEVERITY: Record<string, string> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
};

/** Audit actions as an office user says them ("CREATE" read as a code). */
const ACTION_CHIP_LABELS: Record<string, string> = {
  create: 'Created',
  update: 'Changed',
  delete: 'Deleted',
};

/** AG Grid cell renderer: an action name as a coloured `p-tag` chip. */
@Component({
  selector: 'lpg-action-chip-cell',
  standalone: true,
  imports: [Tag],
  template: `<p-tag [severity]="severity()" [value]="value()" />`,
  styles: [
    `
      :host {
        display: inline-flex;
        vertical-align: middle;
      }
    `,
  ],
})
export class ActionChipCell {
  value = signal('');
  severity = signal<'success' | 'info' | 'danger' | 'secondary'>('secondary');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const raw = typeof params.value === 'string' ? params.value : '';
    this.value.set(ACTION_CHIP_LABELS[raw] ?? raw);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    this.severity.set((ACTION_SEVERITY[params.value] as any) || 'secondary');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/**
 * AG Grid cell renderer for an `entity_id`/`actor_id`-shaped column: shows the
 * row's human-readable display name (falling back to a short id prefix) with
 * the full id available on hover via `pTooltip`, plus a copy-to-clipboard
 * icon — so a raw UUID is never the only thing a user sees.
 */
@Component({
  selector: 'lpg-copyable-id-cell',
  standalone: true,
  imports: [ClipboardModule, TooltipModule],
  template: `
    <div class="copyable-id">
      <span class="copyable-id__text" [pTooltip]="idValue()" tooltipPosition="top">
        {{ displayValue() }}
      </span>
      @if (idValue()) {
        <button
          type="button"
          class="copyable-id__copy"
          [cdkCopyToClipboard]="idValue()"
          aria-label="Copy ID"
          pTooltip="Copy ID"
          tooltipPosition="top"
        >
          <i class="pi pi-copy" aria-hidden="true"></i>
        </button>
      }
    </div>
  `,
  // The copy button never shrinks, the text ellipsises: the icon was clipped
  // at the column edge (QA DA-25).
  styles: [
    `
      .copyable-id {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
        block-size: 100%;
        min-inline-size: 0;
      }
      .copyable-id__text {
        min-inline-size: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .copyable-id__copy {
        flex-shrink: 0;
        display: inline-flex;
        padding: var(--spacing-xs);
        border: 0;
        border-radius: var(--radius-sm);
        background: transparent;
        color: var(--color-text-secondary);
        cursor: pointer;
      }
      .copyable-id__copy:hover,
      .copyable-id__copy:focus-visible {
        color: var(--color-text-primary);
        background: var(--color-surface-overlay);
      }
    `,
  ],
})
export class CopyableIdCell {
  displayValue = signal('');
  idValue = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const row = params.data;
    const field = params.colDef.field;
    if (field === 'entity_id') {
      this.displayValue.set(row.entity_display_name || shortId(params.value));
      this.idValue.set(params.value || '');
    } else if (field === 'actor_id') {
      this.displayValue.set(row.actor_display_name || shortId(params.value) || 'System');
      this.idValue.set(params.value || '');
    } else {
      this.displayValue.set(shortId(params.value));
      this.idValue.set(params.value || '');
    }
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}
