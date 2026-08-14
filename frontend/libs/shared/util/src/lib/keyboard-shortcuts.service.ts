import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, NgZone, inject, signal } from '@angular/core';

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
 */
@Injectable({ providedIn: 'root' })
export class KeyboardShortcutsService {
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly zone = inject(NgZone);
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
      (binding) => {
        // Handle Alt+Key on Mac producing special characters (e.g. Alt+c -> 'ç') by checking event.code fallback
        const isKeyMatch = binding.key === event.key.toLowerCase() || 
                           event.code.toLowerCase() === `key${binding.key}`;
                           
        return isKeyMatch &&
               !!binding.ctrl === (event.ctrlKey || event.metaKey) &&
               !!binding.shift === event.shiftKey &&
               !!binding.alt === event.altKey;
      }
    );

    if (match) {
      event.preventDefault();
      this.zone.run(() => match.handler());
    }
  }
}
