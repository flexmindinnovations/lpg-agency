import { effect, inject, untracked } from '@angular/core';
import { Drawer } from 'primeng/drawer';

/**
 * Runs `reset` each time the `p-drawer` around the calling component closes.
 * Does nothing outside a drawer. Call it from a constructor.
 *
 * A drawer's content is not destroyed when it closes: Angular keeps projected
 * content alive and PrimeNG only takes it off the screen. A component that
 * holds its own state (a chosen file, an open sub-form) would still be showing
 * it the next time, possibly for a different record.
 */
export function onDrawerClose(reset: () => void): void {
  const drawer = inject(Drawer, { optional: true });
  if (!drawer) return;
  let wasOpen = false;
  effect(() => {
    const isOpen = !!drawer.visible();
    if (wasOpen && !isOpen) untracked(reset);
    wasOpen = isOpen;
  });
}
