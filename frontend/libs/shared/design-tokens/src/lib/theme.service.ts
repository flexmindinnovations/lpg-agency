import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import type { Theme } from './tokens';
import { THEMES } from './tokens';

const STORAGE_KEY = 'lpg.theme';

/** `system` follows the OS preference; the three concrete themes override it. */
export type ThemePreference = Theme | 'system';

/**
 * Owns the active theme.
 *
 * Signals-first per ADR-019 — this is component-adjacent state with a tiny
 * surface, so plain signals are correct and a SignalStore would be overkill.
 *
 * The three themes come from `docs/ui/10-color-system.md`. High contrast is not
 * a nicety: WCAG 2.2 AA is a Phase 1 requirement (D-35), and low-vision users
 * need explicit borders where other themes use shadow-based elevation.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  private readonly preferenceSignal = signal<ThemePreference>(this.readStoredPreference());

  /** What the user chose, which may be `system`. */
  readonly preference = this.preferenceSignal.asReadonly();

  /** The theme actually applied, with `system` resolved. */
  readonly activeTheme = computed<Theme>(() => {
    const preference = this.preferenceSignal();
    return preference === 'system' ? this.systemTheme() : preference;
  });

  readonly availableThemes = THEMES;

  constructor() {
    effect(() => this.applyTheme(this.activeTheme(), this.preferenceSignal()));
  }

  setPreference(preference: ThemePreference): void {
    this.preferenceSignal.set(preference);
    try {
      this.document.defaultView?.localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      // Private browsing or a storage quota can make this throw. A theme that
      // does not persist is a far smaller problem than an app that fails to
      // start, so this is deliberately swallowed.
    }
  }

  private applyTheme(theme: Theme, preference: ThemePreference): void {
    const root = this.document.documentElement;
    if (preference === 'system') {
      // Removing the attribute lets the prefers-color-scheme media query in
      // tokens.css take over, rather than pinning a value that would then
      // ignore a mid-session OS change.
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
    root.style.colorScheme = theme === 'dark' ? 'dark' : 'light';
  }

  private systemTheme(): Theme {
    const view = this.document.defaultView;
    if (!view?.matchMedia) return 'light';
    return view.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  private readStoredPreference(): ThemePreference {
    try {
      const stored = this.document.defaultView?.localStorage.getItem(STORAGE_KEY);
      if (stored === 'system' || (THEMES as readonly string[]).includes(stored ?? '')) {
        return stored as ThemePreference;
      }
    } catch {
      // See setPreference.
    }
    return 'system';
  }
}
