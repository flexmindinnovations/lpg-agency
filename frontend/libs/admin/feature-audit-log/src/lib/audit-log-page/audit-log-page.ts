import { HeaderTitlePortalDirective, PageActionsDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  DOCUMENT,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, of } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { Drawer } from 'primeng/drawer';
import { Tag } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import {
  AdminAuditLogService,
  AdminStaffUserService,
  errorMessageFor,
  type AuditLogAction,
  type AuditLogEntryResponse,
} from '@lpg/shared/data-access';
import {
  ActionChipCell,
  DataGridComponent,
  DrawerA11yDirective,
  type DataGridColumn,
  ExportButtonComponent,
  PageHeaderComponent,
} from '@lpg/shared/ui';
import { DATE_INPUT_PLACEHOLDER, formatDisplayDateTime } from '@lpg/shared/util';
import {
  ACTION_LABELS,
  actionLabel,
  actorLabel,
  auditChanges,
  auditLogCsv,
  entityTypeLabel,
  orderIdForEntry,
  recordLabel,
  technicalIdentifiersOf,
} from './audit-log-format';

type ActionSeverity = 'success' | 'info' | 'danger' | 'secondary';

const ACTION_SEVERITY: Record<string, ActionSeverity> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
};

interface Option<T> {
  readonly label: string;
  readonly value: T;
}

/**
 * Admin › Audit Log — who changed what, when (QA UR-04, DA-25).
 *
 * Rows name the record ("ORD000027", "Meena Iyer (CN-000001)") and the person
 * who acted; raw ids live only in the detail drawer. Filters run server-side
 * (record type, action, person, date range); the search box narrows the
 * loaded page.
 */
@Component({
  selector: 'lpg-audit-log-page',
  standalone: true,
  imports: [
    ExportButtonComponent,
    PageActionsDirective,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    FormsModule,
    RouterLink,
    ButtonDirective,
    InputText,
    IconFieldModule,
    InputIconModule,
    Select,
    DatePicker,
    DataGridComponent,

    Drawer,
    DrawerA11yDirective,
    Tag,
    TooltipModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="audit-log-container">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header title="Audit Log" subtitle="Who changed what, and when." />
        </ng-template>
      </div>

      <ng-template lpgPageActions>
        <button
          pButton
          type="button"
          severity="secondary"
          aria-label="Refresh"
          pTooltip="Refresh"
          tooltipPosition="left"
          (click)="reload()"
        >
          <i class="pi pi-refresh" aria-hidden="true"></i>
        </button>
      </ng-template>
      <div class="data-toolbar">
        <div class="data-toolbar__filters">
          <p-iconfield iconPosition="left">
            <p-inputicon class="pi pi-search" />
            <input
              aria-label="Search"
              pInputText
              id="audit_search"
              type="search"
              placeholder="Record or person"
              [ngModel]="searchQuery()"
              (ngModelChange)="searchQuery.set($event)"
            />
          </p-iconfield>
          <p-select
            ariaLabel="Record type"
            inputId="audit_entity"
            [options]="entityOptions()"
            optionLabel="label"
            optionValue="value"
            placeholder="All records"
            [showClear]="true"
            [filter]="entityOptions().length > 8"
            [ngModel]="entityName()"
            (ngModelChange)="entityName.set($event ?? null); reload()"
          />
          <p-select
            ariaLabel="Action"
            inputId="audit_action"
            [options]="actionOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="All actions"
            [showClear]="true"
            [ngModel]="action()"
            (ngModelChange)="action.set($event ?? null); reload()"
          />
          @if (actorOptions().length > 0) {
            <p-select
              ariaLabel="Done by"
              inputId="audit_actor"
              [options]="actorOptions()"
              optionLabel="label"
              optionValue="value"
              placeholder="Anyone"
              [showClear]="true"
              [filter]="true"
              [ngModel]="actorId()"
              (ngModelChange)="actorId.set($event ?? null); reload()"
            />
          }
          <p-datepicker
            ariaLabel="Dates"
            inputId="audit_dates"
            selectionMode="range"
            [readonlyInput]="true"
            [showIcon]="true"
            iconDisplay="input"
            [showButtonBar]="true"
            [placeholder]="datePlaceholder"
            [maxDate]="today"
            [ngModel]="dateRange()"
            (ngModelChange)="onDateRangeChange($event)"
          />
          <span class="data-toolbar__spacer"></span>
          <lpg-export-button [disabled]="entries().length === 0" (export)="exportCsv()" />
        </div>
      </div>

      <section class="grid-section">
        <lpg-data-grid
          [rows]="entries()"
          [columns]="columns"
          [loading]="loading() && entries().length === 0"
          [error]="loadError()"
          (retry)="reload()"
          [searchQuery]="searchQuery()"
          emptyMessage="No activity matches these filters."
          ariaLabel="Audit log"
        />
      </section>

      @if (nextCursor()) {
        <div class="load-more">
          <button
            pButton
            type="button"
            severity="secondary"
            (click)="loadMore()"
            [disabled]="loading()"
          >
            <i class="pi pi-chevron-down" aria-hidden="true"></i><span>Load more</span>
          </button>
        </div>
      }
    </div>

    <p-drawer
      header="Audit entry"
      [(visible)]="drawerVisible"
      position="right"
      [modal]="true"
      [style]="{ width: '100%', maxWidth: '36rem' }"
      [closeOnEscape]="true"
      ariaCloseLabel="Close details"
    >
      @if (selectedEntry(); as entry) {
        <div class="dialog-form">
          <div class="dialog-form__fields">
            <div class="audit-detail-header">
              <div class="audit-detail-header__title">
                @if (orderIdFor(entry); as orderId) {
                  <a
                    [routerLink]="['/orders', orderId]"
                    (click)="drawerVisible = false"
                    class="entity-name entity-link"
                    title="View order details"
                  >
                    <span>{{ recordLabel(entry) }}</span>
                    <i class="pi pi-external-link entity-link__icon" aria-hidden="true"></i>
                  </a>
                } @else {
                  <span class="entity-name">{{ recordLabel(entry) }}</span>
                }
                <p-tag
                  [value]="actionLabel(entry.action)"
                  [severity]="actionSeverity(entry.action)"
                />
              </div>
              <p class="audit-detail-header__meta">
                {{ entityTypeLabel(entry.entity_name) }} · {{ formatTime(entry.performed_at) }} ·
                {{ actorLabel(entry) }}
              </p>
            </div>

            <section class="detail-section">
              <h3 class="section-label">
                {{ entry.action === 'update' ? 'What changed' : 'Details' }}
              </h3>
              @if (changesOf(entry); as changes) {
                @if (changes.length === 0) {
                  <p class="dim">No field-level details were recorded.</p>
                } @else {
                  <table class="changes">
                    <thead>
                      <tr>
                        <th scope="col">Field</th>
                        @if (entry.action !== 'create') {
                          <th scope="col">Before</th>
                        }
                        @if (entry.action !== 'delete') {
                          <th scope="col">{{ entry.action === 'update' ? 'After' : 'Value' }}</th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (change of changes; track change.field) {
                        <tr>
                          <th scope="row">{{ change.field }}</th>
                          @if (entry.action !== 'create') {
                            <td>{{ change.before }}</td>
                          }
                          @if (entry.action !== 'delete') {
                            <td>{{ change.after }}</td>
                          }
                        </tr>
                      }
                    </tbody>
                  </table>
                }
              }
            </section>

            <details class="detail-section ids" open>
              <summary class="section-label-row">
                <span class="section-label">Technical identifiers</span>
                <button
                  pButton
                  type="button"
                  severity="secondary"
                  size="small"
                  class="copy-json-btn"
                  (click)="copyTechnicalIdentifiersAsJson(entry); $event.stopPropagation()"
                  title="Copy all technical identifiers as JSON"
                >
                  <i
                    class="pi"
                    [class.pi-copy]="!copiedJson()"
                    [class.pi-check]="copiedJson()"
                    aria-hidden="true"
                  ></i>
                  <span>{{ copiedJson() ? 'Copied JSON!' : 'Copy as JSON' }}</span>
                </button>
              </summary>
              <dl class="info-grid">
                @for (item of technicalIdentifiers(entry); track item.key) {
                  <div class="info-item">
                    <dt class="info-label">{{ item.label }}</dt>
                    <dd class="info-value">
                      <span class="mono">{{ item.value }}</span>
                      <div class="info-actions">
                        <button
                          type="button"
                          class="copy-icon-btn"
                          (click)="copyValue(item.value, item.key)"
                          [title]="copiedKey() === item.key ? 'Copied!' : 'Copy ' + item.label"
                          [attr.aria-label]="'Copy ' + item.label"
                        >
                          <i
                            class="pi"
                            [class.pi-copy]="copiedKey() !== item.key"
                            [class.pi-check]="copiedKey() === item.key"
                            aria-hidden="true"
                          ></i>
                        </button>
                        @if (item.isOrderId) {
                          <a
                            [routerLink]="['/orders', item.value]"
                            (click)="drawerVisible = false"
                            class="copy-icon-btn"
                            title="View order details"
                            aria-label="View order details"
                          >
                            <i class="pi pi-external-link" aria-hidden="true"></i>
                          </a>
                        }
                      </div>
                    </dd>
                  </div>
                }
              </dl>
            </details>
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="drawerVisible = false">
              Close
            </button>
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

      .load-more {
        display: flex;
        justify-content: center;
        padding-block: var(--spacing-sm);
      }

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
        flex-wrap: wrap;
      }

      .entity-name {
        font-size: var(--typography-heading3-font-size);
        font-weight: var(--typography-heading3-font-weight);
        color: var(--color-text-primary);
      }

      .entity-link {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        color: var(--color-action-primary, #0284c7);
        text-decoration: underline;
        text-underline-offset: 2px;
        cursor: pointer;
      }

      .entity-link:hover {
        color: var(--color-action-primary-hover, #0369a1);
      }

      .entity-link__icon {
        font-size: 0.75rem;
      }

      .section-label-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        cursor: pointer;
        padding-block-end: var(--spacing-xs);
      }

      .copy-json-btn {
        font-size: var(--typography-caption-font-size);
        padding: 2px 8px;
        height: auto;
      }

      .audit-detail-header__meta,
      .dim {
        margin: 0;
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .detail-section {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .section-label {
        margin: 0;
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .ids summary {
        cursor: pointer;
      }

      .changes {
        inline-size: 100%;
        border-collapse: collapse;
        font-size: var(--typography-body-small-font-size);
      }

      .changes th,
      .changes td {
        padding: var(--spacing-xs) var(--spacing-sm);
        border-block-end: var(--border-width) solid var(--color-border-default);
        text-align: start;
        vertical-align: top;
        overflow-wrap: anywhere;
        color: var(--color-text-primary);
      }

      .changes thead th {
        color: var(--color-text-secondary);
        font-weight: var(--typography-label-font-weight);
      }

      .changes tbody th {
        font-weight: var(--typography-label-font-weight);
      }

      .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-md);
        margin: 0;
      }

      .info-item {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        min-inline-size: 0;
      }

      .info-label {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .info-value {
        margin: 0;
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
        overflow-wrap: anywhere;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-xs);
      }

      .info-actions {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }

      .copy-icon-btn {
        background: transparent;
        border: none;
        padding: 4px;
        border-radius: var(--radius-xs, 4px);
        color: var(--color-text-secondary);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition:
          background-color 0.15s,
          color 0.15s;
        font-size: 0.75rem;
      }

      .copy-icon-btn:hover {
        background: var(--color-surface-overlay);
        color: var(--color-text-primary);
      }

      .mono {
        font-family: ui-monospace, monospace;
        font-size: var(--typography-caption-font-size);
      }
    `,
  ],
})
export class AuditLogPage implements OnInit {
  private readonly auditLogService = inject(AdminAuditLogService);
  private readonly staffUserService = inject(AdminStaffUserService);
  private readonly document = inject(DOCUMENT);

  protected readonly entries = signal<AuditLogEntryResponse[]>([]);
  protected readonly nextCursor = signal<string | null>(null);
  protected readonly loading = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly selectedEntry = signal<AuditLogEntryResponse | null>(null);
  protected readonly showDrawer = signal(false);

  protected readonly entityName = signal<string | null>(null);
  protected readonly action = signal<AuditLogAction | null>(null);
  protected readonly actorId = signal<string | null>(null);
  protected readonly dateRange = signal<(Date | null)[] | null>(null);
  protected readonly searchQuery = signal('');

  private readonly entityTypes = signal<string[]>([]);
  protected readonly entityOptions = computed<Option<string>[]>(() =>
    this.entityTypes().map((name) => ({ label: entityTypeLabel(name), value: name })),
  );
  protected readonly actionOptions: Option<AuditLogAction>[] = (
    Object.keys(ACTION_LABELS) as AuditLogAction[]
  ).map((value) => ({ label: ACTION_LABELS[value], value }));
  protected readonly actorOptions = signal<Option<string>[]>([]);

  protected readonly today = new Date();
  protected readonly datePlaceholder = `${DATE_INPUT_PLACEHOLDER} – ${DATE_INPUT_PLACEHOLDER}`;

  protected readonly columns: DataGridColumn<AuditLogEntryResponse>[] = [
    {
      field: 'performed_at',
      header: 'When',
      width: 170,
      valueFormatter: (v) => formatDisplayDateTime(v),
    },
    {
      field: 'entity_display_name',
      header: 'Record',
      flex: 2,
      minWidth: 160,
      valueFormatter: (_v, row) => recordLabel(row),
      onLinkClick: (row) => this.openEntry(row),
    },
    {
      field: 'entity_name',
      header: 'Record type',
      flex: 1,
      valueFormatter: (v) => entityTypeLabel(v),
      priority: 'low',
    },
    {
      field: 'action',
      header: 'Action',
      width: 120,
      cellRenderer: ActionChipCell,
    },
    {
      field: 'actor_display_name',
      header: 'Done by',
      flex: 1.5,
      minWidth: 160,
      valueFormatter: (_v, row) => actorLabel(row),
      tooltipValueGetter: (_v, row) => actorLabel(row),
    },
  ];

  protected get drawerVisible(): boolean {
    return this.showDrawer();
  }
  protected set drawerVisible(value: boolean) {
    this.showDrawer.set(value);
  }

  protected readonly copiedKey = signal<string | null>(null);
  protected readonly copiedJson = signal(false);

  protected readonly formatTime = formatDisplayDateTime;
  protected readonly recordLabel = recordLabel;
  protected readonly actorLabel = actorLabel;
  protected readonly actionLabel = actionLabel;
  protected readonly entityTypeLabel = entityTypeLabel;
  protected readonly changesOf = auditChanges;
  protected readonly technicalIdentifiers = technicalIdentifiersOf;
  protected readonly orderIdFor = orderIdForEntry;

  protected copyValue(val: string, key: string): void {
    if (!val || val === '—') return;
    navigator.clipboard?.writeText(val);
    this.copiedKey.set(key);
    setTimeout(() => {
      if (this.copiedKey() === key) this.copiedKey.set(null);
    }, 2000);
  }

  protected copyTechnicalIdentifiersAsJson(entry: AuditLogEntryResponse): void {
    const ids = technicalIdentifiersOf(entry);
    const obj: Record<string, string> = {};
    for (const item of ids) {
      obj[item.key] = item.value;
    }
    const jsonStr = JSON.stringify(obj, null, 2);
    navigator.clipboard?.writeText(jsonStr);
    this.copiedJson.set(true);
    setTimeout(() => this.copiedJson.set(false), 2000);
  }

  protected actionSeverity(action: string): ActionSeverity {
    return ACTION_SEVERITY[action] ?? 'secondary';
  }

  ngOnInit(): void {
    this.reload();
    this.auditLogService
      .listEntityTypes()
      .pipe(catchError(() => of([] as string[])))
      .subscribe((types) => this.entityTypes.set(types));
    // Shown only to roles that may list staff users; everyone else filters
    // by the other fields.
    this.staffUserService
      .listStaffUsers()
      .pipe(catchError(() => of([])))
      .subscribe((users) =>
        this.actorOptions.set(
          users.map((user) => ({ label: user.email ?? user.id, value: user.id })),
        ),
      );
  }

  protected onDateRangeChange(range: (Date | null)[] | null): void {
    this.dateRange.set(range);
    // The range picker emits on the first click too; wait for both ends.
    if (range && range[0] && !range[1]) return;
    this.reload();
  }

  protected reload(): void {
    this.fetch(null, false);
  }

  protected loadMore(): void {
    const cursor = this.nextCursor();
    if (cursor) this.fetch(cursor, true);
  }

  protected openEntry(entry: AuditLogEntryResponse): void {
    this.selectedEntry.set(entry);
    this.showDrawer.set(true);
  }

  protected exportCsv(): void {
    const blob = new Blob([auditLogCsv(this.entries())], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = this.document.createElement('a');
    link.href = url;
    link.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  private fetch(cursor: string | null, append: boolean): void {
    this.loading.set(true);
    this.loadError.set(null);
    const [from, to] = this.dateRange() ?? [];
    const end = to ?? from;
    // The picked last day is inclusive; the API's upper bound is exclusive.
    const dayAfter = end ? new Date(end.getFullYear(), end.getMonth(), end.getDate() + 1) : null;

    this.auditLogService
      .listAuditLog({
        entityName: this.entityName(),
        action: this.action(),
        actorId: this.actorId(),
        dateFrom: from ? from.toISOString() : null,
        dateTo: dayAfter ? dayAfter.toISOString() : null,
        cursor,
      })
      .subscribe({
        next: (page) => {
          this.entries.set(append ? [...this.entries(), ...page.items] : page.items);
          this.nextCursor.set(page.next_cursor);
          this.loading.set(false);
        },
        error: (error: unknown) => {
          this.loadError.set(errorMessageFor(error));
          this.loading.set(false);
        },
      });
  }
}
