import { Injectable, signal } from '@angular/core';

/**
 * The colours and motion preference a chart needs, resolved from the design
 * tokens in the live document. ECharts options cannot take CSS variables, so
 * the values are read once per theme change here instead of being hard-coded
 * in each chart.
 */
export interface ChartTheme {
  readonly text: string;
  readonly textMuted: string;
  readonly border: string;
  readonly surface: string;
  readonly primary: string;
  readonly accent: string;
  readonly highlight: string;
  readonly success: string;
  readonly warning: string;
  readonly danger: string;
  readonly info: string;
  /** Categorical series colours, in order. Never used to mean a status. */
  readonly series: readonly string[];
  /** The page's font, so ECharts measures label widths with the real glyphs. */
  readonly fontFamily: string;
  readonly reducedMotion: boolean;
}

const TOKEN_FALLBACK = 'currentColor';

function token(style: CSSStyleDeclaration, name: string): string {
  return style.getPropertyValue(name).trim() || TOKEN_FALLBACK;
}

function readTheme(): ChartTheme {
  const style = getComputedStyle(document.documentElement);
  const primary = token(style, '--color-action-primary');
  const accent = token(style, '--primitive-color-accent-500');
  const highlight = token(style, '--primitive-color-flame-orange-500');
  return {
    text: token(style, '--color-text-primary'),
    textMuted: token(style, '--color-text-secondary'),
    border: token(style, '--color-border-default'),
    surface: token(style, '--color-surface-raised'),
    primary,
    accent,
    highlight,
    success: token(style, '--color-status-success'),
    warning: token(style, '--color-status-warning'),
    danger: token(style, '--color-status-danger'),
    info: token(style, '--color-status-info'),
    series: [primary, highlight, accent, token(style, '--color-text-secondary')],
    fontFamily: getComputedStyle(document.body).fontFamily,
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  };
}

/**
 * One shared, app-wide source of the chart theme. A single observer watches
 * the theme attribute and the OS colour scheme; every chart reads the signal,
 * so there is nothing to leak per chart.
 */
@Injectable({ providedIn: 'root' })
export class ChartThemeService {
  private readonly state = signal<ChartTheme | null>(null);

  /** The current theme; `null` outside a browser. */
  readonly theme = this.state.asReadonly();

  constructor() {
    if (typeof document === 'undefined') return;
    this.state.set(readTheme());
    const refresh = () => this.state.set(readTheme());
    const observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme'],
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', refresh);
    window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', refresh);
  }
}
