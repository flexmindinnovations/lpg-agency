import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { AdminAuditLogService, type AuditLogEntryResponse } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

/**
 * Filterable, cursor-paginated audit log viewer — `audit:read`.
 *
 * Cursor-based "load more", not offset pagination, per
 * `docs/ui/14-data-grid-guidelines.md`'s append-only-history guidance
 * (matches `AdminAuditLogService`'s own cursor-based shape).
 */
@Component({
  selector: 'lpg-audit-log-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Audit Log</h1>

      <form
        class="admin-page__filters"
        [formGroup]="filterForm"
        (ngSubmit)="applyFilters()"
        novalidate
      >
        <div class="admin-page__field">
          <label for="filter-entity-name">Entity name</label>
          <input pInputText id="filter-entity-name" type="text" formControlName="entityName" />
        </div>
        <button pButton type="submit">Filter</button>
      </form>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="entries()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Audit log"
        />
      </div>

      @if (nextCursor()) {
        <button
          pButton
          type="button"
          severity="secondary"
          (click)="loadMore()"
          [disabled]="loading()"
        >
          Load more
        </button>
      }
    </div>
  `,
  styles: [
    `
      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
      }

      .admin-page__grid {
        block-size: 400px;
      }

      .admin-page__filters {
        display: flex;
        align-items: flex-end;
        gap: var(--spacing-sm);
      }

      .admin-page__field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
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

  protected readonly filterForm = this.formBuilder.group({
    entityName: [''],
  });

  protected readonly columns: DataGridColumn<AuditLogEntryResponse>[] = [
    { field: 'performed_at', header: 'When', sortable: true },
    { field: 'entity_name', header: 'Entity', sortable: true, filterable: true },
    { field: 'entity_id', header: 'Entity Id' },
    { field: 'action', header: 'Action', sortable: true, filterable: true },
    { field: 'actor_id', header: 'Actor' },
  ];

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
