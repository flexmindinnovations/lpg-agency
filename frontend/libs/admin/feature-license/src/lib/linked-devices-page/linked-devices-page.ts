import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { LicenseService, NotifyService, type LinkedDeviceResponse } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, toSentenceCase } from '@lpg/shared/ui';

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
          <lpg-data-grid
            [rows]="devices()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Linked devices"
          />
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
        margin-block-start: var(--spacing-lg);
      }

    `,
  ],
})
export class LinkedDevicesPage implements OnInit {
  private readonly licenseService = inject(LicenseService);
  private readonly notify = inject(NotifyService);

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
        this.notify.success('Device revoked.');
        this.reload();
      },
    });
  }
}
