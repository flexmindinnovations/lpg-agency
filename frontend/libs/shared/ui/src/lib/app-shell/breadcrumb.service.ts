import { Injectable, signal } from '@angular/core';
import { MenuItem } from 'primeng/api';

/**
 * Global state for the application breadcrumb trail.
 * Feature components can inject this and update the trail.
 */
@Injectable({ providedIn: 'root' })
export class BreadcrumbService {
  private readonly itemsSignal = signal<MenuItem[]>([]);
  private readonly homeSignal = signal<MenuItem | undefined>(undefined);

  readonly items = this.itemsSignal.asReadonly();
  readonly home = this.homeSignal.asReadonly();

  /**
   * Sets the current breadcrumb trail.
   */
  setItems(items: MenuItem[]): void {
    this.itemsSignal.set(items);
  }

  /**
   * Sets the home icon (optional).
   */
  setHome(home: MenuItem | undefined): void {
    this.homeSignal.set(home);
  }

  /**
   * Clears the breadcrumb trail.
   */
  clear(): void {
    this.itemsSignal.set([]);
    this.homeSignal.set(undefined);
  }
}
