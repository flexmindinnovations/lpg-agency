import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { JsonPipe, UpperCasePipe } from '@angular/common';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { Drawer } from 'primeng/drawer';
import { Tag } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { AdminAuditLogService, type AuditLogEntryResponse } from '@lpg/shared/data-access';
import { ActionChipCell, CopyableIdCell, DataGridComponent, formatEntityName, formatTimestamp, type DataGridColumn } from '@lpg/shared/ui';

const ACTION_SEVERITY: Record<string, string> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
};

@Component({
  selector: 'lpg-audit-log-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, 
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    IconFieldModule,
    InputIconModule,
    DataGridComponent,
    Drawer,
    Tag,
    JsonPipe,
    UpperCasePipe,
    TooltipModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="audit-log-container">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Audit Log</h1>
          <p class="page-subtitle">View a chronological record of all system actions.</p>
        </div>
    </ng-template>
      </div>

      <div class="data-toolbar">
        <div class="data-toolbar__filters">
          <p-iconfield styleClass="w-full md:w-80" iconPosition="left">
            <p-inputicon styleClass="pi pi-search" />
            <input
              pInputText
              type="text"
              class="w-full"
              placeholder="Search by entity name..."
              [formControl]="filterForm.controls.entityName"
              (keyup.enter)="applyFilters()"
            />
          </p-iconfield>
        </div>
        <div class="data-toolbar__actions">
          <button pButton type="button" severity="secondary" aria-label="Refresh" (click)="applyFilters()" pTooltip="Refresh" tooltipPosition="left"><i pButtonIcon class="pi pi-refresh"></i></button>
        </div>
      </div>

      <div class="grid-wrapper">
        <lpg-data-grid
          [rows]="entries()"
          [columns]="columns"
          [loading]="loading()"
          [selectionMode]="'single'"
          (selectionChange)="onSelectionChange($event)"
          ariaLabel="Audit log"
        />
      </div>

      @if (nextCursor()) {
        <div class="load-more">
          <button
            pButton
            type="button"
            severity="secondary"
            (click)="loadMore()"
            [disabled]="loading()"
          ><i pButtonIcon class="pi pi-chevron-down"></i><span pButtonLabel>Load more</span></button>
        </div>
      }
    </div>

    <!-- Details Drawer -->
    <p-drawer
      header="Audit Entry Details"
      [(visible)]="drawerVisible"
      position="right"
      [modal]="true"
      styleClass="w-full"
      [style]="{ width: '100%', maxWidth: '36rem' }"
      [closeOnEscape]="true"
      closeAriaLabel="Close details"
    >
      @if (selectedEntry(); as entry) {
        <div class="dialog-form">
          <div class="audit-detail-header">
            <div class="audit-detail-header__title">
              <span class="entity-name">{{ formatEntity(entry.entity_name) }}</span>
              <p-tag
                [value]="entry.action | uppercase"
                [severity]="actionSeverity(entry.action)"
              />
            </div>
            <span class="audit-detail-header__time">{{ formatTime(entry.performed_at) }}</span>
          </div>

          <section class="detail-section">
            <p class="section-label">Identifiers</p>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">Entity</span>
                <span class="info-value">{{ formatEntity(entry.entity_name) }}</span>
                <span class="info-value mono dim">{{ entry.entity_name }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Entity ID</span>
                <span class="info-value mono">{{ entry.entity_id || 'N/A' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Actor ID</span>
                <span class="info-value mono">{{ entry.actor_id || 'System' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Correlation ID</span>
                <span class="info-value mono">{{ entry.correlation_id || 'N/A' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Log ID</span>
                <span class="info-value mono">{{ entry.id }}</span>
              </div>
            </div>
          </section>

          @if (entry.before_state) {
            <section class="detail-section">
              <p class="section-label">Before State</p>
              <pre class="state-code"><code>{{ entry.before_state | json }}</code></pre>
            </section>
          }

          @if (entry.after_state) {
            <section class="detail-section">
              <p class="section-label">After State</p>
              <pre class="state-code"><code>{{ entry.after_state | json }}</code></pre>
            </section>
          }

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="drawerVisible = false">Close</button>
          </div>
        </div>
      }
    </p-drawer>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .audit-log-container {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        block-size: 100%;
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }

      .load-more {
        display: flex;
        justify-content: center;
        padding-block: var(--spacing-sm);
      }

      /* Drawer detail layout */
      .audit-detail-header {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        padding-block-end: var(--spacing-md);
        border-block-end: var(--border-width) solid var(--color-border-default);
      }

      .audit-detail-header__title {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .entity-name {
        font-size: var(--typography-heading3-font-size);
        font-weight: var(--typography-heading3-font-weight);
        color: var(--color-text-primary);
      }

      .audit-detail-header__time {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .detail-section {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-md);
      }

      .info-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .info-label {
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .info-value {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
        word-break: break-all;
      }

      .mono {
        font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
        font-size: var(--typography-caption-font-size);
      }

      .dim {
        color: var(--color-text-secondary);
      }

      .state-code {
        margin: 0;
        padding: var(--spacing-md);
        background: var(--color-surface-sunken);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow-x: auto;
        font-size: var(--typography-caption-font-size);
        font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
        color: var(--color-text-primary);
        line-height: 1.6;
      }
    `,
  ],
})
export class AuditLogPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly auditLogService = inject(AdminAuditLogService);

  protected readonly entries = signal<AuditLogEntryResponse[]>([]);
  protected readonly nextCursor = signal<string | null>(null);
  protected readonly loading = signal(false);
  protected readonly selectedEntry = signal<AuditLogEntryResponse | null>(null);
  protected readonly showDrawer = signal(false);

  protected readonly filterForm = this.formBuilder.group({
    entityName: [''],
  });

  protected readonly columns: DataGridColumn<AuditLogEntryResponse>[] = [
    {
      field: 'performed_at',
      header: 'When',
      sortable: true,
      width: 210,
      valueFormatter: (v) => formatTimestamp(v),
      tooltipValueGetter: (v) => formatTimestamp(v),
    },
    {
      field: 'entity_name',
      header: 'Entity',
      sortable: true,
      filterable: true,
      width: 160,
      valueFormatter: (v) => formatEntityName(v),
      tooltipValueGetter: (v) => String(v ?? ''),
    },
    {
      field: 'action',
      header: 'Action',
      sortable: true,
      filterable: true,
      width: 100,
      cellRenderer: ActionChipCell,
    },
    {
      field: 'entity_id',
      header: 'Entity Details',
      width: 180,
      cellRenderer: CopyableIdCell,
    },
    {
      field: 'actor_id',
      header: 'Actor Details',
      width: 180,
      cellRenderer: CopyableIdCell,
    },
  ];

  protected get drawerVisible(): boolean {
    return this.showDrawer();
  }
  protected set drawerVisible(value: boolean) {
    this.showDrawer.set(value);
  }

  protected readonly formatTime = formatTimestamp;
  protected readonly formatEntity = formatEntityName;

  protected actionSeverity(action: string): 'success' | 'info' | 'danger' | 'secondary' {
    return (ACTION_SEVERITY[action] as 'success' | 'info' | 'danger') ?? 'secondary';
  }

  ngOnInit(): void {
    this.reload();
  }

  protected applyFilters(): void {
    this.reload();
  }

  protected loadMore(): void {
    const cursor = this.nextCursor();
    if (!cursor) {
      return;
    }
    this.fetch(cursor, true);
  }

  protected onSelectionChange(selectedRows: AuditLogEntryResponse[]): void {
    if (selectedRows && selectedRows.length > 0) {
      this.selectedEntry.set(selectedRows[0]);
      this.showDrawer.set(true);
    } else {
      this.selectedEntry.set(null);
      this.showDrawer.set(false);
    }
  }

  private reload(): void {
    this.fetch(null, false);
  }

  private fetch(cursor: string | null, append: boolean): void {
    this.loading.set(true);
    const { entityName } = this.filterForm.getRawValue();

    this.auditLogService.listAuditLog({ entityName: entityName || null, cursor }).subscribe({
      next: (page) => {
        this.entries.set(append ? [...this.entries(), ...page.items] : page.items);
        this.nextCursor.set(page.next_cursor);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
