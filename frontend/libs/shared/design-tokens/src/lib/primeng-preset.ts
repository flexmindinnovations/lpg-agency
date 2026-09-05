import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

/**
 * PrimeNG's design-token preset (ADR-028, ADR-020 amendment).
 *
 * Every value below is `var(--token-name)` or a `color-mix()` derived from
 * one — never a literal hex/px value. That is the entire integration
 * strategy: PrimeNG's own CSS custom properties (`--p-*`) are bound to
 * *our* custom properties (`--color-*`, `--spacing-*`, `--radius-*`,
 * `--component-*`, `--primitive-*`), which `tokens.css` already themes per
 * `[data-theme="dark"|"high-contrast"]`. PrimeNG never needs to know a
 * third theme exists — it renders whatever our cascade resolves for
 * whichever `--color-*` custom property it was pointed at.
 *
 * `definePreset(Aura, {...})` deep-merges onto Aura's base preset, so
 * anything not listed here keeps Aura's own default (used for internal,
 * non-brand-critical shading only — see `tokenScale()` below for why even
 * those mostly end up token-derived too).
 */

/**
 * Synthesizes a Tailwind-shaped 50–950 tint/shade scale from a single
 * token, via CSS's native `color-mix()`. PrimeUIX's base preset expects a
 * full numeric scale for several palette-shaped tokens (`primary`, and the
 * `red`/`green`/`yellow`/`blue` primitives severity components read from) —
 * hand-authoring 11 hex values per colour would be exactly the "second,
 * independent design system" this integration must avoid. Deriving every
 * shade from the one real token instead means there is still only one
 * source of truth; PrimeNG components that need a lighter/darker variant
 * (a hover background, a subtle highlight) get one that is provably related
 * to the token, not a coincidentally-similar Aura default.
 */
function tokenScale(tokenVar: string): Record<number, string> {
  const v = `var(${tokenVar})`;
  return {
    50: `color-mix(in srgb, ${v}, white 95%)`,
    100: `color-mix(in srgb, ${v}, white 90%)`,
    200: `color-mix(in srgb, ${v}, white 75%)`,
    300: `color-mix(in srgb, ${v}, white 55%)`,
    400: `color-mix(in srgb, ${v}, white 30%)`,
    500: v,
    600: `color-mix(in srgb, ${v}, black 12%)`,
    700: `color-mix(in srgb, ${v}, black 28%)`,
    800: `color-mix(in srgb, ${v}, black 44%)`,
    900: `color-mix(in srgb, ${v}, black 60%)`,
    950: `color-mix(in srgb, ${v}, black 75%)`,
  };
}

export const LpgPrimeNgPreset = definePreset(Aura, {
  primitive: {
    borderRadius: {
      none: 'var(--primitive-radius-none)',
      xs: 'var(--primitive-radius-sm)',
      sm: 'var(--primitive-radius-sm)',
      md: 'var(--primitive-radius-md)',
      lg: 'var(--primitive-radius-lg)',
      xl: 'var(--primitive-radius-lg)',
    },
    // Severity colours (Toast, Message, Tag, Badge, ProgressBar, ...) read
    // from these primitive scales rather than a dedicated semantic block —
    // that is PrimeUIX's own architecture, not a choice made here. Deriving
    // them from our status tokens is what makes every severity-aware
    // component automatically theme-token-correct without per-component
    // overrides.
    blue: tokenScale('--color-status-info'),
    green: tokenScale('--color-status-success'),
    red: tokenScale('--color-status-danger'),
    yellow: tokenScale('--color-status-warning'),
    amber: tokenScale('--color-status-warning'),
  },
  semantic: {
    focusRing: {
      width: 'var(--component-focus-ring-width)',
      style: 'solid',
      color: 'var(--component-focus-ring-color)',
      offset: 'var(--component-focus-ring-offset)',
      shadow: 'none',
    },
    disabledOpacity: 'var(--opacity-disabled)',
    iconSize: '1rem',
    // Ties every PrimeNG transition to the same reduced-motion-aware token
    // the rest of the app uses (`tokens.css`'s `@media (prefers-reduced-motion:
    // reduce)` block collapses this to near-zero) — Aura's own default is a
    // flat, unconditional `0.2s` that never respects that preference.
    transitionDuration: 'var(--motion-duration-small)',
    primary: {
      ...tokenScale('--color-action-primary'),
      color: 'var(--color-action-primary)',
      contrastColor: 'var(--color-action-primary-text)',
      hoverColor: 'var(--color-action-primary-hover)',
      activeColor: 'var(--color-action-primary-hover)',
    },
    formField: {
      paddingX: 'var(--spacing-sm)',
      paddingY: 'var(--spacing-xs)',
      borderRadius: 'var(--radius-md)',
      focusRing: {
        width: 'var(--component-focus-ring-width)',
        style: 'solid',
        color: 'var(--component-focus-ring-color)',
        offset: 'var(--component-focus-ring-offset)',
        shadow: 'none',
      },
      background: 'var(--color-surface-base)',
      disabledBackground: 'var(--color-surface-overlay)',
      filledBackground: 'var(--color-surface-raised)',
      filledHoverBackground: 'var(--color-surface-raised)',
      filledFocusBackground: 'var(--color-surface-raised)',
      borderColor: 'var(--color-border-default)',
      hoverBorderColor: 'var(--color-border-strong)',
      focusBorderColor: 'var(--color-action-primary)',
      invalidBorderColor: 'var(--color-status-danger)',
      color: 'var(--color-text-primary)',
      disabledColor: 'var(--color-text-disabled)',
      placeholderColor: 'var(--color-text-secondary)',
      invalidPlaceholderColor: 'var(--color-status-danger)',
      floatLabelColor: 'var(--color-text-secondary)',
      floatLabelFocusColor: 'var(--color-action-primary)',
      floatLabelActiveColor: 'var(--color-text-secondary)',
      floatLabelInvalidColor: 'var(--color-status-danger)',
      iconColor: 'var(--color-text-secondary)',
    },
    content: {
      borderRadius: 'var(--radius-md)',
      background: 'var(--color-surface-base)',
      hoverBackground: 'var(--color-surface-overlay)',
      borderColor: 'var(--color-border-default)',
      color: 'var(--color-text-primary)',
      hoverColor: 'var(--color-text-primary)',
    },
    // Menu/Tree/Breadcrumb read hover/active item background from here, not
    // from `content` — Aura's own default points it at a raw surface
    // primitive (`{surface.100}`/`{surface.800}`) rather than a semantic
    // token, which would have been the one silent gap in an otherwise fully
    // token-driven preset.
    navigation: {
      item: {
        focusBackground: 'var(--color-surface-overlay)',
        activeBackground: 'var(--color-surface-overlay)',
      },
    },
    overlay: {
      select: {
        borderRadius: 'var(--radius-md)',
        background: 'var(--color-surface-base)',
        borderColor: 'var(--color-border-default)',
        color: 'var(--color-text-primary)',
      },
      popover: {
        borderRadius: 'var(--radius-md)',
        padding: 'var(--spacing-sm)',
        background: 'var(--color-surface-base)',
        borderColor: 'var(--color-border-default)',
        color: 'var(--color-text-primary)',
      },
      modal: {
        borderRadius: 'var(--radius-dialog)',
        padding: 'var(--spacing-lg)',
        background: 'var(--color-surface-base)',
        borderColor: 'var(--color-border-default)',
        color: 'var(--color-text-primary)',
      },
    },
    mask: {
      // A dark "smoke" scrim (doc §21) — not the light one Aura's default
      // `{text.color}`-based mix produces on a dark theme. The blur is added
      // on `.p-dialog-mask` / `.p-drawer-mask` in styles.css.
      background: 'color-mix(in srgb, var(--primitive-color-neutral-0), transparent 45%)',
      color: 'var(--color-surface-overlay)',
    },
    surface: {
      0: 'var(--color-surface-base)',
    },
    text: {
      color: 'var(--color-text-primary)',
      hoverColor: 'var(--color-text-primary)',
      mutedColor: 'var(--color-text-secondary)',
      hoverMutedColor: 'var(--color-text-primary)',
    },
    highlight: {
      background: 'color-mix(in srgb, var(--color-action-primary), transparent 88%)',
      focusBackground: 'color-mix(in srgb, var(--color-action-primary), transparent 76%)',
      color: 'var(--color-action-primary)',
      focusColor: 'var(--color-action-primary)',
    },
  },
  components: {
    drawer: {
      // Aura's default gives the header uniform overlay.modal.padding (our
      // --spacing-lg) on all four sides. That creates a large dead gap between
      // the drawer title bar and the first line of content in the form.
      // Reducing just the bottom padding closes that gap while keeping the
      // left/right/top chrome consistent with other modal overlays.
      header: {
        padding: 'var(--spacing-lg) var(--spacing-lg) var(--spacing-sm) var(--spacing-lg)',
      },
    },
    // Deliberately decoupled from `semantic.primary` (Phase 29, Stage 0): the
    // dark theme's --color-action-primary is tuned to read well as *text*
    // against the dark base (4.54:1) but falls short of WCAG AA (4.18:1) as a
    // background under the white label text a filled button needs. These
    // --component-button-primary-* tokens are a step darker specifically for
    // that pairing (5.55:1) — see tokens.css's dark-theme block comment for
    // the full contrast audit. Every other primary-coloured surface (links,
    // icons, focus rings, nav highlight) still reads --color-action-primary
    // via `semantic.primary` above, unaffected by this override.
    button: {
      root: {
        primary: {
          background: 'var(--component-button-primary-background)',
          hoverBackground: 'var(--component-button-primary-background-hover)',
          activeBackground: 'var(--component-button-primary-background-hover)',
          borderColor: 'var(--component-button-primary-background)',
          hoverBorderColor: 'var(--component-button-primary-background-hover)',
          activeBorderColor: 'var(--component-button-primary-background-hover)',
          color: 'var(--component-button-primary-text)',
          hoverColor: 'var(--component-button-primary-text)',
          activeColor: 'var(--component-button-primary-text)',
        },
      },
    },
  },
});
