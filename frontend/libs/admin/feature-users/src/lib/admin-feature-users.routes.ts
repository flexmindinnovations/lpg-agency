import type { Route } from '@angular/router';

/** Mounted at `/admin/users`, gated by `permissionGuard('users:manage')`. */
export const adminFeatureUsersRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./staff-users-page/staff-users-page').then((m) => m.StaffUsersPage),
    title: 'Staff Users',
  },
];
