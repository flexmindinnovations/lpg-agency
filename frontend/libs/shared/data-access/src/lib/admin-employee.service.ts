import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { changeEmployeeStatusApiV1EmployeesEmployeeIdStatusPatch } from './generated/fn/employees/change-employee-status-api-v-1-employees-employee-id-status-patch';
import { getEmployeeApiV1EmployeesEmployeeIdGet } from './generated/fn/employees/get-employee-api-v-1-employees-employee-id-get';
import { listEmployeesApiV1EmployeesGet } from './generated/fn/employees/list-employees-api-v-1-employees-get';
import { registerEmployeeApiV1EmployeesPost } from './generated/fn/employees/register-employee-api-v-1-employees-post';
import { updateEmployeeApiV1EmployeesEmployeeIdPatch } from './generated/fn/employees/update-employee-api-v-1-employees-employee-id-patch';
import {
  ChangeEmployeeStatusRequest,
  EmployeePageResponse,
  EmployeeResponse,
  RegisterEmployeeRequest,
  UpdateEmployeeRequest,
} from './generated/models';

@Injectable({ providedIn: 'root' })
export class AdminEmployeeService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listEmployees(params?: {
    skip?: number;
    limit?: number;
    search?: string;
    role?: string;
    status?: string;
    branch_id?: string;
  }): Observable<EmployeePageResponse> {
    return listEmployeesApiV1EmployeesGet(this.http, this.config.rootUrl, params).pipe(
      map((response) => response.body),
    );
  }

  registerEmployee(data: RegisterEmployeeRequest): Observable<EmployeeResponse> {
    return registerEmployeeApiV1EmployeesPost(this.http, this.config.rootUrl, {
      body: data,
    }).pipe(map((response) => response.body));
  }

  getEmployee(employeeId: string): Observable<EmployeeResponse> {
    return getEmployeeApiV1EmployeesEmployeeIdGet(this.http, this.config.rootUrl, {
      employee_id: employeeId,
    }).pipe(map((response) => response.body));
  }

  updateEmployee(employeeId: string, data: UpdateEmployeeRequest): Observable<EmployeeResponse> {
    return updateEmployeeApiV1EmployeesEmployeeIdPatch(this.http, this.config.rootUrl, {
      employee_id: employeeId,
      body: data,
    }).pipe(map((response) => response.body));
  }

  changeEmployeeStatus(employeeId: string, data: ChangeEmployeeStatusRequest): Observable<EmployeeResponse> {
    return changeEmployeeStatusApiV1EmployeesEmployeeIdStatusPatch(this.http, this.config.rootUrl, {
      employee_id: employeeId,
      body: data,
    }).pipe(map((response) => response.body));
  }
}
