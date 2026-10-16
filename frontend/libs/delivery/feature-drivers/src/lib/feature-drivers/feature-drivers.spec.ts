import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal, type WritableSignal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureDrivers } from './feature-drivers';
import {
  ApiConfiguration,
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
  });
});
