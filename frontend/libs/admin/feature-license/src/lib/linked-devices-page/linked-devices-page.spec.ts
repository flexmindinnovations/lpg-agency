import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import { of } from 'rxjs';
import {
  AdminTenantConfigurationService,
  LicenseService,
  NotifyService,
  PendingDevicesStore,
  type LinkedDeviceResponse,
} from '@lpg/shared/data-access';
import { LinkedDevicesPage } from './linked-devices-page';

function device(overrides: Partial<LinkedDeviceResponse> = {}): LinkedDeviceResponse {
  return {
    id: 'd1',
    app_type: 'driver_app',
    app_version: '1.4.0',
    asset_note: null,
    device_ref: 'AB12CD34',
    display_name: "Ravi's phone",
    last_seen_at: '2026-11-05T09:00:00Z',
    last_user_id: 'u1',
    last_user_name: 'Ravi',
    manufacturer: 'Xiaomi',
    model: 'Redmi 12',
    os_version: 'Android 13',
    phone_ref: null,
    platform: 'android',
    registered_at: '2026-11-05T08:00:00Z',
    removed_at: null,
    status: 'pending',
    status_changed_at: '2026-11-05T08:00:00Z',
    ...overrides,
  };
}

describe('LinkedDevicesPage', () => {
  let license: Record<string, jest.Mock>;
  let config: Record<string, jest.Mock>;
  let pending: { count: jest.Mock; refresh: jest.Mock };
  let notify: { success: jest.Mock };
  let confirmations: Confirmation[];

  function render(options: { mode?: string; devices?: LinkedDeviceResponse[] } = {}) {
    confirmations = [];
    license = {
      listDevices: jest.fn().mockReturnValue(of(options.devices ?? [device()])),
      deviceHistory: jest.fn().mockReturnValue(
        of([
          {
            id: 'h1',
            action: 'registered',
            actor_name: null,
            performed_at: '2026-11-05T08:00:00Z',
            from_status: null,
            to_status: 'pending',
            display_name: null,
          },
        ]),
      ),
      approveDevice: jest.fn().mockReturnValue(of(device({ status: 'approved' }))),
      blockDevice: jest.fn().mockReturnValue(of(device({ status: 'blocked' }))),
      unblockDevice: jest.fn().mockReturnValue(of(device({ status: 'approved' }))),
      removeDevice: jest.fn().mockReturnValue(of(device({ status: 'removed' }))),
      updateDevice: jest.fn().mockReturnValue(of(device({ display_name: 'Van 2' }))),
      deleteDevice: jest.fn().mockReturnValue(of(undefined)),
    };
    config = {
      getEffectiveConfiguration: jest
        .fn()
        .mockReturnValue(of(options.mode ? { config_value: options.mode } : null)),
      setConfiguration: jest.fn().mockReturnValue(of({})),
    };
    pending = { count: jest.fn().mockReturnValue(1), refresh: jest.fn() };
    notify = { success: jest.fn() };
    TestBed.configureTestingModule({
      imports: [LinkedDevicesPage],
      providers: [
        provideNoopAnimations(),
        { provide: LicenseService, useValue: license },
        { provide: AdminTenantConfigurationService, useValue: config },
        { provide: PendingDevicesStore, useValue: pending },
        { provide: NotifyService, useValue: notify },
        {
          provide: ConfirmationService,
          useValue: { confirm: (c: Confirmation) => confirmations.push(c) },
        },
      ],
    });
    const fixture = TestBed.createComponent(LinkedDevicesPage);
    fixture.detectChanges();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- protected members under test
    return { fixture, page: fixture.componentInstance as any };
  }

  it('lists every phone in use and counts the waiting ones on load', () => {
    const { page } = render();

    expect(license['listDevices']).toHaveBeenCalledWith({ appType: null, status: null });
    expect(pending.refresh).toHaveBeenCalled();
    expect(page.devices()).toHaveLength(1);
  });

  it.each([
    ['enforce', 'enforce'],
    ['observe', 'observe'],
    ['bogus', 'off'],
    [undefined, 'off'],
  ])('reads the current device control mode (%s)', (stored, expected) => {
    const { page } = render({ mode: stored });

    expect(page.mode()).toBe(expected);
  });

  it('shows the waiting count on its tab', () => {
    const { page } = render();

    const labels = page.tabOptions().map((t: { label: string }) => t.label);

    expect(labels).toContain('Waiting (1)');
  });

  it('asks the server for the chosen state and app', () => {
    const { page } = render();

    page.chooseTab('pending');
    page.chooseApp('admin_app');

    expect(license['listDevices']).toHaveBeenLastCalledWith({
      appType: 'admin_app',
      status: 'pending',
    });
  });

  it('saves watch-only straight away', () => {
    const { page } = render();

    page.chooseMode('observe');

    expect(config['setConfiguration']).toHaveBeenCalledWith('device_control', 'observe');
    expect(page.mode()).toBe('observe');
  });

  it('asks before switching to approve-only, and says how many phones are waiting', () => {
    const { page } = render();

    page.chooseMode('enforce');

    expect(config['setConfiguration']).not.toHaveBeenCalled();
    expect(confirmations[0].message).toContain('1 phone is still waiting');
    confirmations[0].accept?.();
    expect(config['setConfiguration']).toHaveBeenCalledWith('device_control', 'enforce');
    expect(page.mode()).toBe('enforce');
  });

  it('does not change the mode when the admin says not yet', () => {
    const { page } = render();

    page.chooseMode('enforce');
    confirmations[0].reject?.();

    expect(page.mode()).toBe('off');
  });

  it('opens a phone with its history and the actions its state allows', () => {
    const { page } = render();

    page.open(device());

    expect(license['deviceHistory']).toHaveBeenCalledWith('d1');
    expect(page.history()).toHaveLength(1);
    expect(page.actionsFor(device())).toEqual(['approve', 'block', 'remove']);
    expect(page.nameDraft).toBe("Ravi's phone");
  });

  it('approves without asking, then refreshes the list and the sidebar count', () => {
    const { page } = render();
    page.open(device());
    license['listDevices'].mockClear();

    page.run('approve', device());

    expect(license['approveDevice']).toHaveBeenCalledWith('d1');
    expect(notify.success).toHaveBeenCalledWith("Ravi's phone approved.");
    expect(license['listDevices']).toHaveBeenCalled();
    expect(pending.refresh).toHaveBeenCalledTimes(2);
    expect(page.selected().status).toBe('approved');
  });

  it.each([
    ['block', 'blockDevice'],
    ['remove', 'removeDevice'],
  ])('asks before you %s a phone', (action, method) => {
    const { page } = render();

    page.run(action, device({ status: 'approved' }));

    expect(license[method]).not.toHaveBeenCalled();
    expect(confirmations).toHaveLength(1);
    confirmations[0].accept?.();
    expect(license[method]).toHaveBeenCalledWith('d1');
  });

  it('asks before deleting a phone, whatever its state, and deletes only on yes', () => {
    const { page } = render();

    page.confirmDelete(device({ status: 'removed' }));

    expect(license['deleteDevice']).not.toHaveBeenCalled();
    expect(confirmations).toHaveLength(1);
    expect(confirmations[0].message).toContain('for good');
    confirmations[0].reject?.();
    expect(license['deleteDevice']).not.toHaveBeenCalled();
    confirmations[0].accept?.();
    expect(license['deleteDevice']).toHaveBeenCalledWith('d1');
  });

  it('refreshes the list and the sidebar count after a delete and closes its open drawer', () => {
    const { page } = render();
    page.open(device());
    license['listDevices'].mockClear();

    page.confirmDelete(device());
    confirmations[0].accept?.();

    expect(notify.success).toHaveBeenCalledWith("Ravi's phone deleted.");
    expect(license['listDevices']).toHaveBeenCalled();
    expect(pending.refresh).toHaveBeenCalledTimes(2);
    expect(page.selected()).toBeNull();
    expect(page.drawerVisible).toBe(false);
  });

  it('offers a Delete button for every row of the table', () => {
    const { page } = render();
    const actions = page.columns.find((c: { header: string }) => c.header === 'Actions');

    expect(actions.cellRendererParams.label(device())).toBe("Delete Ravi's phone");
    actions.cellRendererParams.onAction(device());
    expect(confirmations).toHaveLength(1);
  });

  it('unblocks without asking', () => {
    const { page } = render();

    page.run('unblock', device({ status: 'blocked' }));

    expect(license['unblockDevice']).toHaveBeenCalledWith('d1');
    expect(confirmations).toHaveLength(0);
  });

  it('sends only the changed name and note', () => {
    const { page } = render();
    const phone = device();
    page.open(phone);

    page.nameDraft = 'Van 2';
    page.noteDraft = 'IMEI 356938035643809';
    page.saveDetails(phone);

    expect(license['updateDevice']).toHaveBeenCalledWith('d1', {
      displayName: 'Van 2',
      assetNote: 'IMEI 356938035643809',
    });
  });

  it('sends nothing when nothing changed, and never an empty name', () => {
    const { page } = render();
    const phone = device();
    page.open(phone);

    page.saveDetails(phone);
    page.nameDraft = '   ';
    page.saveDetails(phone);

    expect(license['updateDevice']).not.toHaveBeenCalled();
  });

  it('clears the note when it is emptied', () => {
    const { page } = render();
    const phone = device({ asset_note: 'S/N 1' });
    page.open(phone);

    page.noteDraft = '';
    page.saveDetails(phone);

    expect(license['updateDevice']).toHaveBeenCalledWith('d1', { assetNote: '' });
  });

  it('tells the admin why the list is empty when control is off', () => {
    const { page } = render({ devices: [] });

    expect(page.emptyMessage()).toContain('Watch only');
  });
});
