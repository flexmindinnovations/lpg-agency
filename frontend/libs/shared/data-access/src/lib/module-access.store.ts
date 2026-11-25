import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, shareReplay, tap } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listMyModulesApiV1AdminModulesGet } from './generated/fn/administration/list-my-modules-api-v-1-admin-modules-get';

/**
 * Which switchable modules a super admin has turned on for the signed-in
 * agency. Every module is off until the server says it is on, so until the
 * list has loaded (or if it failed to load) no module is shown.
 *
 * This only decides what the dashboard shows. The API refuses a module's calls
 * on its own (`require_module_access`), so this can never grant access. A failed
 * load is not remembered as loaded, so the next route change tries again.
 */
@Injectable({ providedIn: 'root' })
export class ModuleAccessStore {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  private readonly enabled = signal<ReadonlySet<string>>(new Set());
  private readonly loadedSignal = signal(false);
  private inFlight: Observable<void> | null = null;

  /** True once the agency's modules have been fetched. */
  readonly loaded = this.loadedSignal.asReadonly();

  /** Reads a signal, so it is safe inside `computed()` and templates. */
  isEnabled(moduleKey: string): boolean {
    return this.enabled().has(moduleKey);
  }

  /** Fetches the agency's modules. Safe to call again: it shares a request already under way. */
  load(): Observable<void> {
    this.inFlight ??= listMyModulesApiV1AdminModulesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body.filter((m) => m.enabled).map((m) => m.key)),
      tap((keys) => {
        this.enabled.set(new Set(keys));
        this.loadedSignal.set(true);
      }),
      catchError(() => of([])),
      map(() => undefined),
      finalize(() => (this.inFlight = null)),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.inFlight;
  }

  /** Resolves immediately once loaded; otherwise waits for the fetch. For route guards. */
  ensureLoaded(): Observable<void> {
    return this.loadedSignal() ? of(undefined) : this.load();
  }

  clear(): void {
    this.enabled.set(new Set());
    this.loadedSignal.set(false);
    this.inFlight = null;
  }
}
