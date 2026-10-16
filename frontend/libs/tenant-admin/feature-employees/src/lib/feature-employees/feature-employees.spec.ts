import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { ConfirmationService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import {
  AdminBranchService,
  AdminEmployeeService,
  DeliveryService,
  NotifyService,
  type DriverResponse,
  type EmployeeResponse,
} from '@lpg/shared/data-access';
import { FeatureEmployees } from './feature-employees';

const employee = (id: string, role: string, status = 'active'): EmployeeResponse =>
  ({
    id,
    tenant_id: 't1',
    branch_id: 'b1',
    employee_code: `EMP-${id}`,
    first_name: 'Vijay',
    last_name: 'Naidu',
    phone_number: '+919848011005',
    role,
    status,
    email: null,
  }) as EmployeeResponse;

const driver = (employeeId: string, loginId: string | null): DriverResponse =>
  ({
    id: `d-${employeeId}`,
    employee_id: employeeId,
    identity_user_id: loginId,
    status: 'active',
  }) as DriverResponse;

describe('FeatureEmployees', () => {
  let component: FeatureEmployees;
  let fixture: ComponentFixture<FeatureEmployees>;
  let enableDriverLogin: jest.Mock;
  let listDrivers: jest.Mock;
  let success: jest.Mock;

  // Protected members read through a typed view, as other specs in this repo do.
  type Internals = {
    employeeRows: () => { id: string; app_login: string }[];
    canEnableLogin: () => boolean;
    enablingLogin: () => boolean;
    selectedEmployee: { set: (e: EmployeeResponse | null) => void };
    enableLogin: () => void;
    columns: { field: string; header: string }[];
  };
  const internals = () => component as unknown as Internals;

  function create(options: {
    employees: EmployeeResponse[];
    drivers: DriverResponse[] | 'forbidden';
  }): void {
    enableDriverLogin = jest.fn();
    success = jest.fn();
    listDrivers = jest
      .fn()
      .mockReturnValue(
        options.drivers === 'forbidden'
          ? throwError(() => new Error('403'))
          : of({ items: options.drivers, total: options.drivers.length, page: 1, page_size: 200 }),
      );
    TestBed.configureTestingModule({
      imports: [FeatureEmployees],
      providers: [
        ConfirmationService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
        {
          provide: AdminEmployeeService,
          useValue: {
            listEmployees: () =>
              of({ items: options.employees, total: options.employees.length, page: 1 }),
            enableDriverLogin,
          },
        },
        { provide: AdminBranchService, useValue: { listBranches: () => of([]) } },
        { provide: DeliveryService, useValue: { listDrivers } },
        { provide: NotifyService, useValue: { success } },
      ],
    });
    fixture = TestBed.createComponent(FeatureEmployees);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('should create', () => {
    create({ employees: [], drivers: [] });
    expect(component).toBeTruthy();
  });

  describe('App login column', () => {
    it('sits right before Status', () => {
      create({ employees: [], drivers: [] });

      const headers = internals().columns.map((c) => c.header);
      expect(headers.indexOf('App login')).toBe(headers.indexOf('Status') - 1);
    });

    it('says Enabled, Not enabled or a dash depending on the role and the driver profile', () => {
      create({
        employees: [
          employee('with-login', 'driver'),
          employee('without-login', 'driver'),
          employee('no-profile', 'driver'),
          employee('manager', 'manager'),
        ],
        drivers: [driver('with-login', 'user-1'), driver('without-login', null)],
      });

      const labels = Object.fromEntries(
        internals()
          .employeeRows()
          .map((r) => [r.id, r.app_login]),
      );
      expect(labels).toEqual({
        'with-login': 'Enabled',
        'without-login': 'Not enabled',
        'no-profile': 'Not enabled',
        manager: '—',
      });
    });

    it('claims nothing when the user cannot read drivers', () => {
      create({ employees: [employee('e1', 'driver')], drivers: 'forbidden' });

      expect(internals().employeeRows()[0].app_login).toBe('—');
    });
  });

  describe('enable login', () => {
    it('is offered for an active driver without a login, and when the state is unknown', () => {
      create({
        employees: [employee('e1', 'driver')],
        drivers: [driver('e1', null)],
      });
      internals().selectedEmployee.set(employee('e1', 'driver'));
      expect(internals().canEnableLogin()).toBe(true);

      TestBed.resetTestingModule();
      create({ employees: [employee('e1', 'driver')], drivers: 'forbidden' });
      internals().selectedEmployee.set(employee('e1', 'driver'));
      expect(internals().canEnableLogin()).toBe(true);
    });

    it('is not offered when the driver already has a login, for staff, or for inactive drivers', () => {
      create({
        employees: [employee('e1', 'driver')],
        drivers: [driver('e1', 'user-1')],
      });

      internals().selectedEmployee.set(employee('e1', 'driver'));
      expect(internals().canEnableLogin()).toBe(false);
      internals().selectedEmployee.set(employee('e2', 'manager'));
      expect(internals().canEnableLogin()).toBe(false);
      internals().selectedEmployee.set(employee('e3', 'driver', 'inactive'));
      expect(internals().canEnableLogin()).toBe(false);
    });

    it('enables the login, says who can now sign in and refreshes the login state', () => {
      create({ employees: [employee('e1', 'driver')], drivers: [driver('e1', null)] });
      enableDriverLogin.mockReturnValue(
        of({ employee_id: 'e1', driver_id: 'd1', login_created: true, driver_created: false }),
      );
      internals().selectedEmployee.set(employee('e1', 'driver'));

      internals().enableLogin();

      expect(enableDriverLogin).toHaveBeenCalledWith('e1');
      expect(success).toHaveBeenCalledTimes(1);
      const [message, title] = success.mock.calls[0] as [string, string];
      expect(title).toBe('Driver app login enabled');
      expect(message).toContain('Vijay Naidu can now sign in to the Driver App with +919848011005');
      expect(message).not.toContain('PENDING');
      expect(listDrivers).toHaveBeenCalledTimes(2); // once on load, once after enabling
      expect(internals().enablingLogin()).toBe(false);
    });

    it('tells the admin to complete the licence when a driver profile had to be created', () => {
      create({ employees: [employee('e1', 'driver')], drivers: [] });
      enableDriverLogin.mockReturnValue(
        of({ employee_id: 'e1', driver_id: 'd1', login_created: true, driver_created: true }),
      );
      internals().selectedEmployee.set(employee('e1', 'driver'));

      internals().enableLogin();

      expect((success.mock.calls[0] as [string])[0]).toContain('PENDING');
    });

    it('stops the spinner and stays quiet when the server refuses (the global handler explains)', () => {
      create({ employees: [employee('e1', 'driver')], drivers: [driver('e1', null)] });
      enableDriverLogin.mockReturnValue(throwError(() => new Error('409')));
      internals().selectedEmployee.set(employee('e1', 'driver'));

      internals().enableLogin();

      expect(success).not.toHaveBeenCalled();
      expect(internals().enablingLogin()).toBe(false);
    });
  });
});
