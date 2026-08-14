import { Route } from '@angular/router';
import { FeatureEmployees } from './feature-employees/feature-employees';

export const tenantAdminFeatureEmployeesRoutes: Route[] = [
  {
    path: '',
    component: FeatureEmployees,
    title: 'Employees',
  },
];
