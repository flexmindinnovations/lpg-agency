import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, shareReplay, tap } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listMyModulesApiV1AdminModulesGet } from './generated/fn/administration/list-my-modules-api-v-1-admin-modules-get';

/**
 * Which switchable modules (AI Command Center, Scales, Cylinder Units) a super
 * admin has turned off for the signed-in agency. Every module is on until the
 * server says otherwise.
 *
 * This only decides what the dashboard shows. The API refuses a switched-off
 * module's calls on its own (`require_module`), so a stale or failed fetch here
 * can hide too little but never grants access — which is why a failed load
 * leaves everything visible instead of blocking the whole app.
 */
@Injectable({ providedIn: 'root' })
export class ModuleAccessStore {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  private readonly disabled = signal<ReadonlySet<string>>(new Set());
  private readonly loadedSignal = signal(false);
  private inFlight: Observable<void> | null = null;

  /** True once the agency's modules have been fetched (or the fetch failed). */
  readonly loaded = this.loadedSignal.asReadonly();

  /** Reads a signal, so it is safe inside `computed()` and templates. */
  isEnabled(moduleKey: string): boolean {
    return !this.disabled().has(moduleKey);
  }

  /** Fetches the agency's modules. Safe to call again: it shares a request already under way. */
  load(): Observable<void> {
    this.inFlight ??= listMyModulesApiV1AdminModulesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body.filter((m) => !m.enabled).map((m) => m.key)),
      tap((keys) => this.disabled.set(new Set(keys))),
      catchError(() => of([])),
      map(() => undefined),
      tap(() => this.loadedSignal.set(true)),
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
    this.disabled.set(new Set());
    this.loadedSignal.set(false);
    this.inFlight = null;
  }
}
