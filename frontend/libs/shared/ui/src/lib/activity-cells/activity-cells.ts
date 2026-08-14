import { Component, signal } from '@angular/core';
import { ClipboardModule } from '@angular/cdk/clipboard';
import { Tag } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';

/** Formats an ISO-8601 timestamp to a readable "11 Aug 2026, 17:23:18" form. */
export function formatTimestamp(value: unknown): string {
  if (!value || typeof value !== 'string') return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
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
    this.value.set(params.value?.toUpperCase() || '');
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
    <div style="display: flex; align-items: center; gap: 0.5rem; height: 100%;">
      <span class="cell-mono" [pTooltip]="idValue()" tooltipPosition="top">
        {{ displayValue() }}
      </span>
      @if (idValue()) {
        <i
          class="pi pi-copy"
          style="cursor: pointer; color: var(--color-text-secondary); font-size: 0.875rem;"
          [cdkCopyToClipboard]="idValue()"
          pTooltip="Copy ID"
          tooltipPosition="top"
        ></i>
      }
    </div>
  `,
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
