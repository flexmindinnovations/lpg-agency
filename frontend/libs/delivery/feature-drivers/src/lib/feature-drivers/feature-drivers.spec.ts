import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal, type WritableSignal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureDrivers, licenceState } from './feature-drivers';
import {
  AdminEmployeeService,
  ApiConfiguration,
  DeliveryService,
  NotifyService,
  type DriverResponse,
  type EmployeeResponse,
} from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

describe('FeatureDrivers', () => {
  let component: FeatureDrivers;
  let fixture: ComponentFixture<FeatureDrivers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureDrivers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureDrivers);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('Name column', () => {
    // Protected members read through a typed view, as other specs in this repo do;
    // `detectChanges()` is deliberately not called so `ngOnInit` fires no requests.
    type Internals = {
      allEmployees: WritableSignal<EmployeeResponse[]>;
      drivers: WritableSignal<DriverResponse[]>;
      driverRows: () => { employee_id: string; employee_name: string }[];
      columns: { field: string; header: string }[];
    };
    const internals = () => component as unknown as Internals;
    const employee = (id: string, first: string, last: string, code: string) =>
      ({ id, first_name: first, last_name: last, employee_code: code }) as EmployeeResponse;
    const driver = (id: string, employeeId: string) =>
      ({ id, employee_id: employeeId, status: 'active' }) as DriverResponse;

    it('puts a Name column right after Employee Code', () => {
      const headers = internals().columns.map((c) => c.header);

      expect(headers.slice(0, 3)).toEqual(['Employee Code', 'Name', 'License Number']);
      expect(internals().columns[1].field).toBe('employee_name');
    });

    it('shows each driver’s full name from their employee record', () => {
      internals().allEmployees.set([
        employee('e1', 'Ravi', 'Kumar', 'EMP-1003'),
        employee('e2', 'Demo', 'Driver', 'EMP0003'),
      ]);
      internals().drivers.set([driver('d1', 'e1'), driver('d2', 'e2')]);

      expect(
        internals()
          .driverRows()
          .map((r) => r.employee_name),
      ).toEqual(['Ravi Kumar', 'Demo Driver']);
    });

    it('falls back to a dash when the employee record is not available', () => {
      internals().drivers.set([driver('d1', 'unknown-employee')]);

      expect(internals().driverRows()[0].employee_name).toBe('—');
    });

    it('fills in names when the employee list arrives after the drivers', () => {
      internals().drivers.set([driver('d1', 'e1')]);
      expect(internals().driverRows()[0].employee_name).toBe('—');

      internals().allEmployees.set([employee('e1', 'Ravi', 'Kumar', 'EMP-1003')]);

      expect(internals().driverRows()[0].employee_name).toBe('Ravi Kumar');
    });

    it('prefers the name the driver API returns over the employee directory', () => {
      internals().drivers.set([{ ...driver('d1', 'e9'), name: 'Asha Patil' }]);

      expect(internals().driverRows()[0].employee_name).toBe('Asha Patil');
    });
  });

  describe('licence expiry warning', () => {
    type Internals = {
      drivers: WritableSignal<DriverResponse[]>;
      licenceWarnings: () => { expired: number; expiring: number; text: string };
    };
    const iso = (offsetDays: number) => {
      const d = new Date();
      d.setDate(d.getDate() + offsetDays);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };

    it('counts expired and soon-expiring licences across all drivers', () => {
      const internals = component as unknown as Internals;
      internals.drivers.set([
        { id: 'a', license_expiry_date: iso(-1) },
        { id: 'b', license_expiry_date: iso(5) },
        { id: 'c', license_expiry_date: iso(200) },
        { id: 'd', license_expiry_date: null },
      ] as DriverResponse[]);

      expect(internals.licenceWarnings()).toEqual({
        expired: 1,
        expiring: 1,
        text: '1 driver licence has expired. 1 expires within 30 days. Renew them from the driver details.',
      });
    });
  });
});

describe('licenceState', () => {
  const today = new Date(2026, 9, 20);

  it('classifies a licence against today', () => {
    expect(licenceState(null, today)).toBe('missing');
    expect(licenceState('2026-10-19', today)).toBe('expired');
    expect(licenceState('2026-10-20', today)).toBe('expiring');
    expect(licenceState('2026-11-19', today)).toBe('expiring');
    expect(licenceState('2026-11-20', today)).toBe('valid');
  });
});

describe('FeatureDrivers — enable app login', () => {
  const vijay = {
    id: 'e1',
    first_name: 'Vijay',
    last_name: 'Naidu',
    employee_code: 'EMP-1005',
    phone_number: '+919848011005',
  } as EmployeeResponse;
  const withoutLogin = {
    id: 'd1',
    employee_id: 'e1',
    identity_user_id: null,
    status: 'active',
  } as DriverResponse;
  const withLogin = { ...withoutLogin, identity_user_id: 'u1' } as DriverResponse;

  type Internals = {
    selectedDriver: { set: (d: DriverResponse | null) => void; (): DriverResponse | null };
    enablingLogin: () => boolean;
    enableLogin: (d: DriverResponse) => void;
  };

  let component: FeatureDrivers;
  let enableDriverLogin: jest.Mock;
  let listDrivers: jest.Mock;
  let success: jest.Mock;

  function create(): void {
    enableDriverLogin = jest.fn();
    success = jest.fn();
    listDrivers = jest.fn().mockReturnValue(of({ items: [withoutLogin], total: 1, page: 1 }));
    TestBed.configureTestingModule({
      imports: [FeatureDrivers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
        {
          provide: AdminEmployeeService,
          useValue: {
            listEmployees: () => of({ items: [vijay], total: 1, page: 1 }),
            enableDriverLogin,
          },
        },
        { provide: DeliveryService, useValue: { listDrivers } },
        { provide: NotifyService, useValue: { success } },
      ],
    });
    const fixture = TestBed.createComponent(FeatureDrivers);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  const internals = () => component as unknown as Internals;

  it('enables the login for the driver’s employee, says who can sign in, and refreshes the drawer', () => {
    create();
    enableDriverLogin.mockReturnValue(
      of({ employee_id: 'e1', driver_id: 'd1', login_created: true, driver_created: false }),
    );
    listDrivers.mockReturnValue(of({ items: [withLogin], total: 1, page: 1 }));
    internals().selectedDriver.set(withoutLogin);

    internals().enableLogin(withoutLogin);

    expect(enableDriverLogin).toHaveBeenCalledWith('e1');
    expect(success).toHaveBeenCalledWith(
      'Vijay Naidu can now sign in to the Driver App with +919848011005.',
      'Driver app login enabled',
    );
    // The open drawer now shows the refreshed row, so it flips to "Enabled".
    expect(internals().selectedDriver()?.identity_user_id).toBe('u1');
    expect(internals().enablingLogin()).toBe(false);
  });

  it('stops the spinner and stays quiet when the server refuses (the global handler explains)', () => {
    create();
    enableDriverLogin.mockReturnValue(throwError(() => new Error('409')));
    internals().selectedDriver.set(withoutLogin);

    internals().enableLogin(withoutLogin);

    expect(success).not.toHaveBeenCalled();
    expect(internals().enablingLogin()).toBe(false);
    expect(internals().selectedDriver()?.identity_user_id).toBeNull();
  });
});
