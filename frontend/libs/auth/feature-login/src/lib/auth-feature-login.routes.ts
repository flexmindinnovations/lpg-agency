import { Route } from '@angular/router';

/**
 * Mounted at `/login` in `apps/dashboard/src/app/app.routes.ts`, outside
 * `ShellLayout`/`authGuard` (ADR-036) — every route here must be reachable
 * without an existing session.
 */
export const authFeatureLoginRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./login-page/login-page').then((m) => m.LoginPage),
    title: 'Sign in',
  },
  {
    path: 'forgot-password',
    loadComponent: () =>
      import('./forgot-password-page/forgot-password-page').then((m) => m.ForgotPasswordPage),
    title: 'Reset your password',
  },
  {
    path: 'reset-password',
    loadComponent: () =>
      import('./reset-password-page/reset-password-page').then((m) => m.ResetPasswordPage),
    title: 'Choose a new password',
  },
];
