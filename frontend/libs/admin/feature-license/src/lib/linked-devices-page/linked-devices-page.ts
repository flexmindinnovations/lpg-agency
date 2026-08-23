import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MessageService } from 'primeng/api';
import { LicenseService, type AppError, type LinkedDeviceResponse } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, toSentenceCase } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong revoking the device. Please try again.';
  }
}

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` (same issue fixed for Platform
 * Flags' "Default" column) — this swaps that for plain "Active"/"Revoked"
 * text. */
@Component({
  selector: 'lpg-device-status-cell',
  standalone: true,
  template: `{{ label() }}`,
})
class DeviceStatusCell {
  protected readonly label = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    this.label.set(params.value ? 'Active' : 'Revoked');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/**
 * This tenant's linked devices (Customer/Driver/Warehouse app instances) —
 * `agency_admin`, `license:manage_tenant`.
 */
@Component({
  selector: 'lpg-linked-devices-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Linked Devices</h1>
          <p class="page-subtitle">Customer, Driver, and Warehouse app instances registered to this tenant.</p>
        </div>
    </ng-template>
      </div>

      @if (!loading() && devices().length === 0) {
        <div class="empty-state">
          <i class="pi pi-mobile empty-state__icon"></i>
          <p class="empty-state__title">No devices linked yet</p>
          <p class="empty-state__description">Devices appear here once an app instance registers.</p>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="devices()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Linked devices"
            />
          </div>
        </section>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .admin-page {
        display: flex;
        flex-direction: column;
        block-size: 100%;
      }

      .grid-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-block-size: 0;
        margin-block-start: var(--spacing-lg);
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }
    `,
  ],
})
export class LinkedDevicesPage implements OnInit {
  private readonly licenseService = inject(LicenseService);
  private readonly messageService = inject(MessageService);

  protected readonly devices = signal<LinkedDeviceResponse[]>([]);
  protected readonly loading = signal(false);

  protected readonly columns: DataGridColumn<LinkedDeviceResponse>[] = [
    {
      field: 'app_type',
      header: 'App',
      sortable: true,
      filterable: true,
      valueFormatter: (value) => toSentenceCase(String(value)),
    },
    { field: 'display_name', header: 'Device' },
    { field: 'device_identifier', header: 'Identifier' },
    { field: 'registered_at', header: 'First Linked', sortable: true },
    { field: 'last_seen_at', header: 'Last Seen', sortable: true },
    {
      field: 'is_active',
      header: 'Status',
      cellRenderer: DeviceStatusCell,
    },
    {
      field: 'id',
      header: '',
      // A boolean-valued field re-used purely as the link column's
      // clickable label ("Revoke" for an active device, nothing for an
      // already-revoked one) — `onLinkClick` itself no-ops defensively for
      // a row that's already revoked.
      valueFormatter: (_value, row) => (row.is_active ? 'Revoke' : ''),
      onLinkClick: (row) => {
        if (row.is_active) this.revoke(row.id);
      },
    },
  ];

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.licenseService.listDevices().subscribe({
      next: (devices) => {
        this.devices.set(devices);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected revoke(deviceId: string): void {
    this.licenseService.revokeDevice(deviceId).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Device revoked.' });
        this.reload();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
