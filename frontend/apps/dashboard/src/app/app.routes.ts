import { Route } from '@angular/router';

/**
 * Routing foundation.
 *
 * Feature routes are lazy-loaded per feature library, matching the Nx boundary
 * rule (ADR-018) — so a route boundary and a module boundary are the same line.
 *
 * No business routes exist yet. `authGuard`, `tenantGuard` and
 * `permissionGuard` arrive in Phase 6 with Authentication.
 */
export const appRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./home/home').then((m) => m.Home),
    title: 'LPG Agency Management Platform',
  },
  {
    path: '**',
    loadComponent: () => import('./not-found/not-found').then((m) => m.NotFound),
    title: 'Page not found',
  },
];
