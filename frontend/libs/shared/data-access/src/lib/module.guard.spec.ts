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
import { ModuleAccessStore } from './module-access.store';
import { moduleGuard } from './module.guard';

async function runGuard(disabled: string[], moduleKey: string): Promise<unknown> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: AuthService, useValue: { ensureSessionRestored: () => of(true) } },
      {
        provide: ModuleAccessStore,
        useValue: {
          ensureLoaded: () => of(undefined),
          isEnabled: (key: string) => !disabled.includes(key),
        },
      },
    ],
  });
  const result = TestBed.runInInjectionContext(() =>
    moduleGuard(moduleKey)({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
  return isObservable(result) ? firstValueFrom(result) : result;
}

describe('moduleGuard', () => {
  it('lets the user in while the module is on', async () => {
    expect(await runGuard(['cylinder_units'], 'scales')).toBe(true);
  });

  it('sends the user home when the module is switched off', async () => {
    const tree = await runGuard(['scales'], 'scales');
    expect(TestBed.inject(Router).serializeUrl(tree as UrlTree)).toBe('/');
  });
});
