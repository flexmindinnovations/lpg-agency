import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';
import { Dialog } from 'primeng/dialog';
import { Tag } from 'primeng/tag';
import type { ChipSeverity } from '../status-chip-cell/status-chip-cell';

export interface PreviewTag {
  label: string;
  severity: ChipSeverity;
}

export interface PreviewField {
  label: string;
  value: string;
}

export interface PreviewData {
  title: string;
  subtitle?: string;
  tags?: PreviewTag[];
  /** Rendered two-per-row. */
  fields: PreviewField[];
  /** Rendered one-per-row below `fields` — for longer values like addresses. */
  fullWidthFields?: PreviewField[];
}

/**
 * Read-only "quick view" dialog for a single entity, opened from a link/button
 * elsewhere in the page (a customer, a staff member, an order, ...) without
 * navigating away. One shared component/markup/CSS instead of every feature
 * re-implementing the same dialog — drive it by calling `open()` then
 * `showData()`/`showError()` once the lookup resolves.
 */
@Component({
  selector: 'lpg-preview-dialog',
  imports: [Dialog, Tag],
  template: `
    <p-dialog
      [visible]="visible()"
      (visibleChange)="!$event && close()"
      [header]="header()"
      [modal]="true"
      [dismissableMask]="true"
      [style]="{ width: '28rem' }"
    >
      @if (loading()) {
        <p class="preview-loading">Loading…</p>
      } @else if (data(); as d) {
        <div class="preview-content">
          <div class="preview-header">
            <h3>{{ d.title }}</h3>
            @if (d.subtitle) {
              <p class="preview-subtitle">{{ d.subtitle }}</p>
            }
          </div>
          @if (d.tags?.length) {
            <div class="preview-tags">
              @for (tag of d.tags; track tag.label) {
                <p-tag [value]="tag.label" [severity]="tag.severity" />
              }
            </div>
          }
          @if (d.fields.length) {
            <div class="preview-grid">
              @for (field of d.fields; track field.label) {
                <div class="info-item">
                  <span class="info-label">{{ field.label }}</span>
                  <span class="info-value">{{ field.value }}</span>
                </div>
              }
            </div>
          }
          @for (field of d.fullWidthFields; track field.label) {
            <div class="info-item">
              <span class="info-label">{{ field.label }}</span>
              <span class="info-value">{{ field.value }}</span>
            </div>
          }
        </div>
      }
    </p-dialog>
  `,
  styleUrl: './preview-dialog.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PreviewDialog {
  readonly header = input('Details');

  protected readonly visible = signal(false);
  protected readonly loading = signal(false);
  protected readonly data = signal<PreviewData | null>(null);

  /** Opens the dialog in its loading state — call before the lookup starts. */
  open(): void {
    this.visible.set(true);
    this.loading.set(true);
    this.data.set(null);
  }

  showData(data: PreviewData): void {
    this.data.set(data);
    this.loading.set(false);
  }

  close(): void {
    this.visible.set(false);
  }
}
