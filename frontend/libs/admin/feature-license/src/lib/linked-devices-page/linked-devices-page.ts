import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { ConfirmationService } from 'primeng/api';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import {
  AdminTenantConfigurationService,
  LicenseService,
  NotifyService,
  PendingDevicesStore,
  type DeviceHistoryEntryResponse,
  type DeviceStatus,
  type LinkedDeviceResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  DetailItemComponent,
  DetailListComponent,
  DrawerA11yDirective,
  HeaderTitlePortalDirective,
  PageHeaderComponent,
  SectionCardComponent,
  StatusChipCell,
  ToggleGroupComponent,
  formatTimestamp,
  type DataGridColumn,
} from '@lpg/shared/ui';
import {
  CONTROL_MODES,
  STATUS_LABELS,
  STATUS_SEVERITY,
  allowedActions,
  appLabel,
  appWithVersion,
  historyVerb,
  osLabel,
  phoneModel,
  statusLabel,
  statusSeverity,
  type DeviceControlMode,
} from './device-labels';

type StatusTab = 'all' | DeviceStatus;
type DeviceAction = 'approve' | 'block' | 'unblock' | 'remove';

const DEVICE_CONTROL_KEY = 'device_control';

/**
 * Settings > Linked Devices (ADR-071): the phones running the Driver and
 * Admin apps, the ones waiting for approval, and the switch that decides
 * whether approval is required at all. Agency admin only
 * (`license:manage_tenant`); the server re-checks every action.
 */
@Component({
  selector: 'lpg-linked-devices-page',
  standalone: true,
  imports: [
    FormsModule,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    DataGridComponent,
    SectionCardComponent,
    DetailListComponent,
    DetailItemComponent,
    DrawerA11yDirective,
    ButtonDirective,
    Drawer,
    InputText,
    Select,
    ToggleGroupComponent,
    Tag,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header
            title="Linked Devices"
            subtitle="Phones using your Driver and Admin apps."
          />
        </ng-template>
      </div>

      <lpg-section-card class="control">
        <h2 class="section-title" id="device-control-title">Who can use the apps</h2>
        <lpg-toggle-group
          [options]="modeOptions"
          [value]="mode()"
          (valueChange)="chooseMode($event)"
          [disabled]="savingMode()"
          ariaLabel="Who can use the apps"
        />
        <p class="control__help" aria-live="polite">{{ modeHelp() }}</p>
      </lpg-section-card>

      <div class="filters">
        <p-select
          [options]="tabOptions()"
          [ngModel]="tab()"
          (ngModelChange)="chooseTab($event)"
          optionLabel="label"
          optionValue="value"
          ariaLabel="Show phones by state"
          fluid
        />
        <p-select
          [options]="appOptions"
          [ngModel]="appFilter()"
          (ngModelChange)="chooseApp($event)"
          optionLabel="label"
          optionValue="value"
          ariaLabel="Filter by app"
          fluid
        />
      </div>

      <section class="grid-section">
        <lpg-data-grid
          [rows]="devices()"
          [columns]="columns"
          [loading]="loading()"
          [pageSize]="15"
          ariaLabel="Linked devices"
          emptyTitle="No phones here"
          [emptyMessage]="emptyMessage()"
        />
      </section>
    </div>

    <p-drawer
      [(visible)]="drawerVisible"
      position="right"
      [modal]="true"
      [style]="{ width: '100%', maxWidth: '34rem' }"
      [closeOnEscape]="true"
      closeAriaLabel="Close"
      (onHide)="closeDrawer()"
    >
      <ng-template #header>
        <div class="font-bold text-lg">{{ selected()?.display_name ?? 'Phone' }}</div>
      </ng-template>

      @if (selected(); as device) {
        <div class="drawer">
          <div class="drawer__status">
            <p-tag [value]="label(device.status)" [severity]="severity(device.status)" />
            <span class="drawer__app">{{ appName(device.app_type) }}</span>
          </div>

          @if (device.status === 'pending') {
            <p class="drawer__note">
              {{ device.last_user_name ?? 'Someone' }} signed in on this phone and is waiting for
              you. If you do not know this phone, block it.
            </p>
          }

          <div class="drawer__actions">
            @for (action of actionsFor(device); track action) {
              <button
                pButton
                type="button"
                [severity]="action === 'approve' || action === 'unblock' ? 'primary' : 'danger'"
                [outlined]="action === 'remove'"
                [disabled]="busy()"
                (click)="run(action, device)"
              >
                {{ actionLabel(action) }}
              </button>
            }
          </div>

          <lpg-detail-list>
            <lpg-detail-item label="Model">{{ model(device) }}</lpg-detail-item>
            <lpg-detail-item label="Software">{{ os(device) }}</lpg-detail-item>
            <lpg-detail-item label="App">{{ appVersion(device) }}</lpg-detail-item>
            <lpg-detail-item label="Last signed in">{{
              device.last_user_name ?? '—'
            }}</lpg-detail-item>
            <lpg-detail-item label="First seen">{{ time(device.registered_at) }}</lpg-detail-item>
            <lpg-detail-item label="Last seen">{{ time(device.last_seen_at) }}</lpg-detail-item>
            <lpg-detail-item label="Phone reference"
              ><code>{{ device.device_ref }}</code></lpg-detail-item
            >
            @if (device.phone_ref) {
              <lpg-detail-item label="Hardware reference"
                ><code>{{ device.phone_ref }}</code></lpg-detail-item
              >
            }
          </lpg-detail-list>
          <p class="drawer__hint">
            References let you tell phones apart. The same hardware reference on two entries means
            the app was reinstalled on the same phone.
          </p>

          @if (device.status !== 'removed') {
            <form class="drawer__form" (ngSubmit)="saveDetails(device)">
              <label for="device-name">Name</label>
              <input
                pInputText
                id="device-name"
                name="name"
                maxlength="60"
                [(ngModel)]="nameDraft"
                [fluid]="true"
                required
              />
              <label for="device-note">IMEI or serial number (optional)</label>
              <input
                pInputText
                id="device-note"
                name="note"
                maxlength="64"
                [(ngModel)]="noteDraft"
                [fluid]="true"
                autocomplete="off"
              />
              <p class="drawer__hint">
                Type it from the phone's box or settings. The apps cannot read it themselves, so
                this is a note for your records, not a check.
              </p>
              <div class="drawer__actions">
                <button pButton type="submit" [disabled]="busy() || !nameDraft.trim()">
                  Save details
                </button>
              </div>
            </form>
          }

          <h3 class="drawer__heading">History</h3>
          @if (history().length === 0) {
            <p class="drawer__hint">Nothing recorded yet.</p>
          } @else {
            <ol class="history">
              @for (entry of history(); track entry.id) {
                <li>
                  <strong>{{ verb(entry.action) }}</strong>
                  @if (entry.actor_name) {
                    <span> by {{ entry.actor_name }}</span>
                  }
                  <span class="history__time">{{ time(entry.performed_at) }}</span>
                </li>
              }
            </ol>
          }
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

      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        block-size: 100%;
      }

      .section-title {
        margin: 0 0 var(--spacing-sm);
        font-size: var(--typography-body-font-size);
        font-weight: var(--typography-label-font-weight);
      }

      .control__help {
        margin: var(--spacing-sm) 0 0;
        color: var(--color-text-secondary);
        max-inline-size: 60ch;
      }

      /* Two dropdowns side by side on one line (state, then app); they stack on
         a narrow screen. */
      .filters {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 14rem));
        gap: var(--spacing-md);
        align-items: center;
      }

      @media (max-width: 480px) {
        .filters {
          grid-template-columns: minmax(0, 1fr);
        }
      }

      .grid-section {
        min-block-size: 0;
      }

      .drawer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .drawer__status {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .drawer__app,
      .drawer__hint,
      .history__time {
        color: var(--color-text-secondary);
      }

      .drawer__hint {
        margin: 0;
        font-size: var(--typography-caption-font-size);
      }

      .drawer__note {
        margin: 0;
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-md);
        background: var(--color-surface-overlay);
      }

      .drawer__actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }

      .drawer__form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .drawer__heading {
        margin: var(--spacing-sm) 0 0;
        font-size: var(--typography-body-font-size);
      }

      .history {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        margin: 0;
        padding-inline-start: var(--spacing-lg);
      }

      .history__time {
        margin-inline-start: var(--spacing-sm);
        font-size: var(--typography-caption-font-size);
      }
    `,
  ],
})
export class LinkedDevicesPage implements OnInit {
  private readonly licenseService = inject(LicenseService);
  private readonly configService = inject(AdminTenantConfigurationService);
  private readonly notify = inject(NotifyService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly pending = inject(PendingDevicesStore);

  protected readonly devices = signal<LinkedDeviceResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly tab = signal<StatusTab>('all');
  protected readonly appFilter = signal<string>('all');
  protected readonly pendingCount = computed(() => this.pending.count());

  protected readonly mode = signal<DeviceControlMode>('off');
  protected readonly savingMode = signal(false);
  protected readonly modeOptions = [...CONTROL_MODES];
  protected readonly modeHelp = computed(
    () => CONTROL_MODES.find((m) => m.value === this.mode())?.help ?? '',
  );

  protected readonly selected = signal<LinkedDeviceResponse | null>(null);
  protected readonly history = signal<DeviceHistoryEntryResponse[]>([]);
  protected readonly busy = signal(false);
  protected drawerVisible = false;
  protected nameDraft = '';
  protected noteDraft = '';

  protected readonly tabOptions = computed(() => [
    { label: 'All states', value: 'all' as const, icon: 'pi pi-list' },
    {
      label: this.pendingCount() > 0 ? `Waiting (${this.pendingCount()})` : 'Waiting',
      value: 'pending' as const,
      icon: 'pi pi-clock',
    },
    { label: 'Approved', value: 'approved' as const, icon: 'pi pi-check-circle' },
    { label: 'Blocked', value: 'blocked' as const, icon: 'pi pi-ban' },
    { label: 'Removed', value: 'removed' as const, icon: 'pi pi-trash' },
  ]);

  protected readonly appOptions = [
    { label: 'All apps', value: 'all' },
    { label: 'Driver app', value: 'driver_app' },
    { label: 'Admin app', value: 'admin_app' },
  ];

  protected readonly emptyMessage = computed(() => {
    if (this.mode() === 'off') {
      return 'Device control is off, so phones are not recorded. Choose "Watch only" above to start building your list.';
    }
    return this.tab() === 'pending'
      ? 'No phone is waiting for approval.'
      : 'Phones appear here after someone signs in to the Driver or Admin app.';
  });

  protected readonly columns: DataGridColumn<LinkedDeviceResponse>[] = [
    {
      field: 'display_name',
      header: 'Phone',
      sortable: true,
      flex: 2,
      minWidth: 170,
      // The phone's name opens its details, like the name column elsewhere.
      onLinkClick: (row) => this.open(row),
    },
    {
      field: 'model',
      minWidth: 150,
      header: 'Model',
      valueFormatter: (_value, row) => phoneModel(row),
      priority: 'low',
    },
    {
      field: 'os_version',
      minWidth: 120,
      header: 'Software',
      valueFormatter: (_value, row) => osLabel(row),
      priority: 'low',
    },
    {
      field: 'app_type',
      minWidth: 150,
      header: 'App',
      sortable: true,
      valueFormatter: (_value, row) => appWithVersion(row),
    },
    {
      field: 'last_user_name',
      minWidth: 190,
      header: 'Signed in as',
      valueFormatter: (value) => (value ? String(value) : '—'),
      priority: 'low',
    },
    {
      field: 'status',
      minWidth: 110,
      header: 'State',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { labelMap: STATUS_LABELS, severityMap: STATUS_SEVERITY },
    },
    {
      field: 'registered_at',
      minWidth: 160,
      header: 'First seen',
      sortable: true,
      valueFormatter: (value) => formatTimestamp(value),
      priority: 'low',
    },
    {
      field: 'last_seen_at',
      minWidth: 160,
      header: 'Last seen',
      sortable: true,
      valueFormatter: (value) => formatTimestamp(value),
    },
  ];

  ngOnInit(): void {
    this.loadMode();
    this.reload();
    this.pending.refresh();
  }

  // -- Template helpers ---------------------------------------------------------

  protected label = statusLabel;
  protected severity = statusSeverity;
  protected appName = appLabel;
  protected model = phoneModel;
  protected os = osLabel;
  protected appVersion = appWithVersion;
  protected verb = historyVerb;
  protected time = formatTimestamp;

  protected actionsFor(device: LinkedDeviceResponse): readonly DeviceAction[] {
    return allowedActions(device.status);
  }

  protected actionLabel(action: DeviceAction): string {
    return { approve: 'Approve', block: 'Block', unblock: 'Unblock', remove: 'Remove' }[action];
  }

  // -- Filters ------------------------------------------------------------------

  protected chooseTab(tab: StatusTab): void {
    this.tab.set(tab);
    this.reload();
  }

  protected chooseApp(app: string): void {
    this.appFilter.set(app);
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    const tab = this.tab();
    const app = this.appFilter();
    this.licenseService
      .listDevices({
        appType: app === 'all' ? null : (app as 'driver_app' | 'admin_app'),
        status: tab === 'all' ? null : tab,
      })
      .subscribe({
        next: (devices) => {
          this.devices.set(devices);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  // -- Device control mode ------------------------------------------------------

  private loadMode(): void {
    this.configService.getEffectiveConfiguration(DEVICE_CONTROL_KEY).subscribe({
      next: (config) => {
        const value = config?.config_value;
        this.mode.set(value === 'observe' || value === 'enforce' ? value : 'off');
      },
      error: () => undefined,
    });
  }

  protected chooseMode(next: DeviceControlMode): void {
    if (next === this.mode()) return;
    if (next === 'enforce') {
      const waiting = this.pendingCount();
      this.confirmation.confirm({
        header: 'Only approved phones will work?',
        message:
          waiting > 0
            ? `${waiting} phone${waiting === 1 ? ' is' : 's are'} still waiting and will be signed out until you approve ${waiting === 1 ? 'it' : 'them'}. Approve the phones your team uses first.`
            : 'Phones you have not approved will be signed out. Check that every phone your team uses is approved first.',
        acceptLabel: 'Switch on',
        rejectLabel: 'Not yet',
        accept: () => this.saveMode(next),
      });
      return;
    }
    this.saveMode(next);
  }

  private saveMode(next: DeviceControlMode): void {
    this.savingMode.set(true);
    this.configService.setConfiguration(DEVICE_CONTROL_KEY, next).subscribe({
      next: () => {
        this.mode.set(next);
        this.savingMode.set(false);
        this.notify.success('Saved.');
        this.reload();
      },
      error: () => this.savingMode.set(false),
    });
  }

  // -- One phone ----------------------------------------------------------------

  protected open(device: LinkedDeviceResponse): void {
    this.selected.set(device);
    this.nameDraft = device.display_name;
    this.noteDraft = device.asset_note ?? '';
    this.history.set([]);
    this.drawerVisible = true;
    this.licenseService.deviceHistory(device.id).subscribe({
      next: (entries) => this.history.set(entries),
      error: () => undefined,
    });
  }

  protected closeDrawer(): void {
    this.selected.set(null);
  }

  protected run(action: DeviceAction, device: LinkedDeviceResponse): void {
    const messages: Partial<
      Record<DeviceAction, { header: string; message: string; accept: string }>
    > = {
      block: {
        header: 'Block this phone?',
        message: `"${device.display_name}" will be signed out at once and cannot use the app until you unblock it. Anything not yet sent stays on the phone.`,
        accept: 'Block',
      },
      remove: {
        header: 'Remove this phone?',
        message: `"${device.display_name}" will be signed out and taken off your list. If it signs in again it will wait for approval.`,
        accept: 'Remove',
      },
    };
    const ask = messages[action];
    if (!ask) {
      this.apply(action, device);
      return;
    }
    this.confirmation.confirm({
      header: ask.header,
      message: ask.message,
      acceptLabel: ask.accept,
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.apply(action, device),
    });
  }

  private apply(action: DeviceAction, device: LinkedDeviceResponse): void {
    const call = {
      approve: () => this.licenseService.approveDevice(device.id),
      block: () => this.licenseService.blockDevice(device.id),
      unblock: () => this.licenseService.unblockDevice(device.id),
      remove: () => this.licenseService.removeDevice(device.id),
    }[action]();
    this.busy.set(true);
    call.subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.notify.success(this.doneMessage(action, updated.display_name));
        this.afterChange(updated);
      },
      error: () => this.busy.set(false),
    });
  }

  private doneMessage(action: DeviceAction, name: string): string {
    const done = { approve: 'approved', block: 'blocked', unblock: 'unblocked', remove: 'removed' };
    return `${name} ${done[action]}.`;
  }

  protected saveDetails(device: LinkedDeviceResponse): void {
    const name = this.nameDraft.trim();
    if (!name) return;
    const changes: { displayName?: string; assetNote?: string } = {};
    if (name !== device.display_name) changes.displayName = name;
    if (this.noteDraft.trim() !== (device.asset_note ?? '')) {
      changes.assetNote = this.noteDraft.trim();
    }
    if (Object.keys(changes).length === 0) return;
    this.busy.set(true);
    this.licenseService.updateDevice(device.id, changes).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.notify.success('Saved.');
        this.afterChange(updated);
      },
      error: () => this.busy.set(false),
    });
  }

  /** Refresh the list, the open drawer and the sidebar badge after a change. */
  private afterChange(updated: LinkedDeviceResponse): void {
    this.selected.set(updated);
    this.nameDraft = updated.display_name;
    this.noteDraft = updated.asset_note ?? '';
    this.licenseService.deviceHistory(updated.id).subscribe({
      next: (entries) => this.history.set(entries),
      error: () => undefined,
    });
    this.reload();
    this.pending.refresh();
  }
}
