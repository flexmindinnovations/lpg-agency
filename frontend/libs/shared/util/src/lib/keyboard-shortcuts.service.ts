import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';

export interface ShortcutBinding {
  /** Lower-case `KeyboardEvent.key`, e.g. `k`, `n`, `escape`. */
  readonly key: string;
  readonly ctrl?: boolean;
  readonly shift?: boolean;
  readonly alt?: boolean;
  readonly description: string;
  readonly handler: () => void;
}

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
};

/**
 * Central registry for global keyboard shortcuts.
 *
 * One service rather than per-component listeners, per
 * `knowledge/09-engineering-standards.md`. Scattered listeners produce
 * conflicting bindings that nobody can audit, and there is no single place to
 * render a "keyboard shortcuts" help dialog from.
 *
 * The catalogue of bindings is `docs/ui/16-keyboard-shortcuts.md`. Nothing is
 * registered in Phase 1 — the shortcuts are for features that do not exist yet.
 */
@Injectable({ providedIn: 'root' })
export class KeyboardShortcutsService {
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly bindings = signal<readonly ShortcutBinding[]>([]);

  /** Registered bindings, for rendering a shortcuts help dialog. */
  readonly registered = this.bindings.asReadonly();

  constructor() {
    const listener = (event: KeyboardEvent) => this.handle(event);
    this.document.addEventListener('keydown', listener);
    this.destroyRef.onDestroy(() => this.document.removeEventListener('keydown', listener));
  }

  /** Register a shortcut. Returns a function that unregisters it. */
  register(binding: ShortcutBinding): () => void {
    this.bindings.update((current) => [...current, binding]);
    return () => this.bindings.update((current) => current.filter((b) => b !== binding));
  }

  private handle(event: KeyboardEvent): void {
    // Never hijack typing. Escape is the exception — closing a dialog from
    // inside a focused field is exactly what a user expects.
    if (isEditableTarget(event.target) && event.key.toLowerCase() !== 'escape') return;

    const match = this.bindings().find(
      (binding) =>
        binding.key === event.key.toLowerCase() &&
        !!binding.ctrl === (event.ctrlKey || event.metaKey) &&
        !!binding.shift === event.shiftKey &&
        !!binding.alt === event.altKey,
    );

    if (match) {
      event.preventDefault();
      match.handler();
    }
  }
}
