import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { firstValueFrom, isObservable, of } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';
import { permissionGuard } from './permission.guard';

async function runGuard(role: string, permissions: string[], code: string): Promise<unknown> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: AuthService, useValue: { ensureSessionRestored: () => of(true) } },
      {
        provide: AuthTokenStore,
        useValue: { principal: () => ({ role, permissions: new Set(permissions) }) },
      },
    ],
  });
  const result = TestBed.runInInjectionContext(() =>
    permissionGuard(code)({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
  return isObservable(result) ? firstValueFrom(result) : result;
}

function url(tree: unknown): string {
  return TestBed.inject(Router).serializeUrl(tree as UrlTree);
}

describe('permissionGuard', () => {
  it('allows a principal holding the permission', async () => {
    expect(await runGuard('manager', ['orders:read'], 'orders:read')).toBe(true);
  });

  it('shows the no-access page to a tenant user without it', async () => {
    expect(url(await runGuard('accountant', [], 'inventory:read'))).toBe('/no-access');
  });

  it('sends a platform session back to the Platform Console', async () => {
    expect(url(await runGuard('super_admin', [], 'license:manage_platform'))).toBe('/platform');
  });
});
