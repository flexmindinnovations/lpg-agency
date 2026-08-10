import type { Route } from '@angular/router';

/** Mounted at `/admin/audit-log`, gated by `permissionGuard('audit:read')`. */
export const adminFeatureAuditLogRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./audit-log-page/audit-log-page').then((m) => m.AuditLogPage),
    title: 'Audit Log',
  },
];
