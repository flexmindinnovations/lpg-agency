import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { map, switchMap } from 'rxjs';
import { AuthService } from './auth.service';
import { ModuleAccessStore } from './module-access.store';

/**
 * Sends the user home when a super admin has switched the module off for their
 * agency. A UI convenience only: the API refuses the module's calls regardless
 * (`require_module`). Waits for the module list, so a direct link or refresh on
 * a switched-off module redirects instead of flashing the page.
 */
export function moduleGuard(moduleKey: string): CanActivateFn {
  return () => {
    const authService = inject(AuthService);
    const modules = inject(ModuleAccessStore);
    const router = inject(Router);

    return authService.ensureSessionRestored().pipe(
      switchMap(() => modules.ensureLoaded()),
      map(() => (modules.isEnabled(moduleKey) ? true : router.createUrlTree(['/']))),
    );
  };
}
