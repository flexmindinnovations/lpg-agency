import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listEmployeesApiV1EmployeesGet } from './generated/fn/employees/list-employees-api-v-1-employees-get';
import { registerEmployeeApiV1EmployeesPost } from './generated/fn/employees/register-employee-api-v-1-employees-post';
import { EmployeePageResponse, EmployeeResponse, RegisterEmployeeRequest } from './generated/models';

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
}
