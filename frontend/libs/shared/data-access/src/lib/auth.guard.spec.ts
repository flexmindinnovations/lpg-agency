import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { firstValueFrom, isObservable, of } from 'rxjs';
import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

async function runGuard(url: string, restored: boolean): Promise<unknown> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: AuthService, useValue: { ensureSessionRestored: () => of(restored) } },
    ],
  });
  const result = TestBed.runInInjectionContext(() =>
    authGuard({} as ActivatedRouteSnapshot, { url } as RouterStateSnapshot),
  );
  return isObservable(result) ? firstValueFrom(result) : result;
}

describe('authGuard', () => {
  it('lets a restored session through', async () => {
    expect(await runGuard('/orders', true)).toBe(true);
  });

  it('sends a signed-out visitor to /login with the page they wanted', async () => {
    const result = (await runGuard('/orders/42?tab=items', false)) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(result)).toBe(
      '/login?returnUrl=%2Forders%2F42%3Ftab%3Ditems',
    );
  });

  it('adds no returnUrl for Home', async () => {
    const result = (await runGuard('/', false)) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(result)).toBe('/login');
  });
});
