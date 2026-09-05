import { Injectable, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { KeyboardShortcutsService } from '@lpg/shared/util';

/**
 * Owns the command palette's open state and focus round-trip. Global
 * `Ctrl/Cmd+K` is registered through `KeyboardShortcutsService` so it shows
 * up in any future shortcuts-help view (one caveat: that service ignores
 * key events fired from within an input, so `Ctrl/Cmd+K` won't open the
 * palette while a text field is focused — acceptable for now).
 */
@Injectable({ providedIn: 'root' })
export class CommandPaletteService {
  private readonly document = inject(DOCUMENT);
  private readonly shortcuts = inject(KeyboardShortcutsService);

  private readonly openState = signal(false);
  readonly isOpen = this.openState.asReadonly();

  /** The element to hand focus back to when the palette closes. */
  private returnFocusEl: HTMLElement | null = null;

  constructor() {
    this.shortcuts.register({
      key: 'k',
      ctrl: true,
      description: 'Open the command palette',
      handler: () => this.toggle(),
    });
  }

  open(): void {
    if (this.openState()) return;
    const active = this.document.activeElement;
    this.returnFocusEl = active instanceof HTMLElement ? active : null;
    this.openState.set(true);
  }

  close(): void {
    if (!this.openState()) return;
    this.openState.set(false);
    // Defer so the palette has finished tearing down before focus moves.
    queueMicrotask(() => {
      this.returnFocusEl?.focus?.();
      this.returnFocusEl = null;
    });
  }

  toggle(): void {
    if (this.openState()) {
      this.close();
    } else {
      this.open();
    }
  }
}
