import { Route } from '@angular/router';
import { authGuard } from '@lpg/shared/data-access';
import { ShellLayout } from './shell/shell-layout';

/**
 * Routing foundation.
 *
 * Feature routes are lazy-loaded per feature library, matching the Nx boundary
 * rule (ADR-018) — so a route boundary and a module boundary are the same line.
 *
 * `/login` is a sibling of the shell-wrapped tree, not a child of it
 * (ADR-036) — it must be reachable without an existing session, and without
 * the sidebar/top-bar chrome `ShellLayout` renders. It is declared first so
 * the router matches it before ever trying `ShellLayout`'s own catch-all
 * child route. Every other route sits under `ShellLayout`, gated by
 * `authGuard`.
 */
export const appRoutes: Route[] = [
  {
    path: 'login',
    loadChildren: () => import('@lpg/auth/feature-login').then((m) => m.authFeatureLoginRoutes),
  },
  {
    path: '',
    component: ShellLayout,
    canActivate: [authGuard],
    children: [
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
    ],
  },
];
