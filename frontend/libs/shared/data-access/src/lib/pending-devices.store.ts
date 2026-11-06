import { Injectable, Injector, inject, signal } from '@angular/core';
import { LicenseService } from './license.service';

/**
 * How many phones are waiting for the agency admin to approve them — the
 * number behind the Settings badge in the sidebar. Held in memory only; the
 * server stays the source of truth, so a failed fetch just leaves the last
 * known number rather than hiding the badge or raising an error.
 */
@Injectable({ providedIn: 'root' })
export class PendingDevicesStore {
  // Resolved on first use, so a screen that only reads the count does not
  // need the HTTP stack set up.
  private readonly injector = inject(Injector);
  private readonly countSignal = signal(0);

  readonly count = this.countSignal.asReadonly();

  refresh(): void {
    this.injector
      .get(LicenseService)
      .pendingDeviceCount()
      .subscribe({
        next: (count) => this.countSignal.set(count),
        error: () => undefined,
      });
  }

  /** The page already knows the number (it just listed the waiting phones). */
  set(count: number): void {
    this.countSignal.set(count);
  }

  clear(): void {
    this.countSignal.set(0);
  }
}
