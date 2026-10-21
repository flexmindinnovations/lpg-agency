import {
  Directive,
  ElementRef,
  HostListener,
  OnDestroy,
  PLATFORM_ID,
  effect,
  inject,
  signal,
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Drawer } from 'primeng/drawer';
import type { PrimeNG } from 'primeng/config';

/**
 * Retro-fits the ARIA modal-dialog contract onto PrimeNG's `p-drawer`.
 *
 * Out of the box the drawer ships only a Tab focus-trap (`pFocusTrap`) and
 * renders as `role="complementary"`: it never moves focus into the panel on
 * open, never marks the rest of the app inert, and never restores focus on
 * close. The visible mask blocks the mouse, but a keyboard user Tabs straight
 * from the trigger into the page behind it, and a screen-reader virtual cursor
 * roams the background freely — WCAG 2.4.3 (Focus Order) and the ARIA APG
 * dialog pattern.
 *
 * This directive, applied by selector to every `<p-drawer>`, adds on open:
 * `role="dialog"` + `aria-modal="true"`, a label wired from the drawer heading,
 * initial focus moved into the panel, and `inert` on every background region;
 * on close it clears `inert` and returns focus to the element that opened the
 * drawer. Add `DrawerA11yDirective` to the host component's `imports`.
 *
 * Assumptions (both hold across this app): one modal drawer open at a time, and
 * the drawer renders inline. `app.config.ts` sets PrimeNG's `overlayAppendTo`
 * to `body` app-wide so select / date / autocomplete lists inside a drawer are
 * never clipped by its scrolling body (QA UR-01) — that default would move the
 * drawer itself to `<body>` too, so this directive pins its own drawer inline
 * (see `keepDrawerInline`). Inner overlays mount on `<body>` after this
 * snapshot and stay interactive.
 *
 * It also names the header close button ("Close"), which PrimeNG renders as
 * an icon-only button with no accessible name (QA DO-35, axe `button-name`).
 */
/** Overlays that can open above a modal drawer and must stay interactive. */
const OVERLAY_SELECTOR =
  'p-dialog, p-confirmdialog, p-confirm-dialog, p-toast, p-drawer, .p-dialog, .p-drawer, .p-toast';

@Directive({
  // Augments PrimeNG's `<p-drawer>` by element — there is no attribute to hook,
  // and adding one at 40-plus call sites is exactly the churn this avoids.
  // eslint-disable-next-line @angular-eslint/directive-selector
  selector: 'p-drawer',
  standalone: true,
})
export class DrawerA11yDirective implements OnDestroy {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
  private readonly drawer = inject(Drawer, { optional: true });

  /** Element focus returns to when the drawer closes. */
  private trigger: HTMLElement | null = null;
  /** Background elements this instance marked `inert`, reverted on close. */
  private readonly inerted: HTMLElement[] = [];

  constructor() {
    this.keepDrawerInline();
    // PrimeNG's `Drawer` only emits `(onHide)` when closed via its internal header 'X'
    // button (`close()`). When closed programmatically (e.g. `visible.set(false)` from
    // a form Cancel/Close button or Escape handler), `Drawer` calls `hide(false)` on
    // transition leave, which deliberately suppresses `(onHide)`. Reactively monitoring
    // `drawer.visible()` guarantees `inert` is immediately cleared and focus restored
    // regardless of which trigger or binding closed the drawer.
    if (this.drawer && this.isBrowser) {
      effect(() => {
        const isVisible = this.drawer?.visible();
        if (!isVisible && (this.inerted.length > 0 || this.trigger !== null)) {
          this.onHide();
        }
      });
    }
  }

  @HostListener('onShow')
  protected onShow(): void {
    if (!this.isBrowser) return;
    this.trigger = (document.activeElement as HTMLElement | null) ?? null;

    // The panel + mask are in the DOM by the time `onShow` fires; a rAF guards
    // against the enter-motion still settling before we read/focus it.
    requestAnimationFrame(() => {
      const panel = this.host.nativeElement.querySelector<HTMLElement>('.p-drawer');
      if (!panel) return;

      // PrimeNG's template hard-codes `role="complementary"` (it treats the
      // drawer as a sidebar landmark); a modal task panel is a dialog.
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'true');
      this.labelPanel(panel);
      this.nameCloseButton(panel);
      this.inertBackground();
      this.focusInto(panel);
    });
  }

  @HostListener('onHide')
  @HostListener('visibleChange', ['$event'])
  protected onHide(visible?: unknown): void {
    if (!this.isBrowser) return;
    if (visible === true) return;
    this.revert();
    const previous = this.trigger;
    this.trigger = null;
    if (previous && document.body.contains(previous)) {
      previous.focus({ preventScroll: true });
    }
  }

  ngOnDestroy(): void {
    // Route change (or *ngIf) while the drawer is open — never leave the app inert.
    this.revert();
  }

  /**
   * The app default `overlayAppendTo: 'body'` is meant for dropdown panels; the
   * drawer reads the same setting, and on `<body>` it would escape the
   * background-inerting walk below. Give this drawer a view of the config
   * whose `overlayAppendTo` is `self`, leaving every other setting shared.
   * Runs before the drawer first reads it (its `$appendTo` is a lazy computed).
   */
  private keepDrawerInline(): void {
    const drawer = this.drawer;
    if (!drawer) return;
    const inline: PrimeNG = Object.create(drawer.config);
    inline.overlayAppendTo = signal('self');
    drawer.config = inline;
  }

  /** PrimeNG's header close button is icon-only and unnamed. */
  private nameCloseButton(panel: HTMLElement): void {
    const close = panel.querySelector<HTMLElement>('.p-drawer-close-button');
    if (close && !close.hasAttribute('aria-label')) close.setAttribute('aria-label', 'Close');
  }

  /** Wire `aria-labelledby` from the drawer's heading when nothing labels it. */
  private labelPanel(panel: HTMLElement): void {
    if (panel.hasAttribute('aria-label') || panel.hasAttribute('aria-labelledby')) return;
    const heading = panel.querySelector<HTMLElement>(
      '.p-drawer-title, .p-drawer-header h1, .p-drawer-header h2, .p-drawer-header h3',
    );
    if (!heading) return;
    if (!heading.id) {
      heading.id = `lpg-drawer-title-${Math.random().toString(36).slice(2, 9)}`;
    }
    panel.setAttribute('aria-labelledby', heading.id);
  }

  /** Move focus to the first usable control (fallback: close button, then panel). */
  private focusInto(panel: HTMLElement): void {
    const scope = panel.querySelector<HTMLElement>('.p-drawer-content') ?? panel;
    const candidates = scope.querySelectorAll<HTMLElement>(
      'input, select, textarea, button, a[href], [tabindex]:not([tabindex="-1"])',
    );
    const target =
      Array.from(candidates).find(
        (el) =>
          !el.hasAttribute('disabled') &&
          !el.hasAttribute('hidden') &&
          (el as HTMLInputElement).type !== 'hidden' &&
          !el.classList.contains('p-hidden-focusable') &&
          el.closest('[hidden]') === null,
      ) ??
      panel.querySelector<HTMLElement>('.p-drawer-close-button') ??
      panel;
    if (target === panel) panel.tabIndex = -1;
    target.focus({ preventScroll: true });
  }

  /**
   * Walk from the drawer host up toward `<body>`, marking every sibling that
   * isn't on the drawer's ancestor path as `inert`. Stops before `<body>` so
   * app-level siblings of the shell stay live. The `<p-drawer>` host itself is
   * never inerted, so its mask keeps working.
   */
  private inertBackground(): void {
    let node: HTMLElement = this.host.nativeElement;
    let parent: HTMLElement | null = node.parentElement;
    while (parent && parent !== document.body) {
      for (const sibling of Array.from(parent.children)) {
        if (sibling === node || !(sibling instanceof HTMLElement)) continue;
        this.inertExceptOverlays(sibling);
      }
      node = parent;
      parent = node.parentElement;
    }
  }

  /**
   * Inert `el` unless it is, or contains, an overlay that can open on top of
   * the drawer (a dialog, confirm dialog, toast or another drawer). Overlays
   * are usually wrapped in a feature component (e.g. a
   * `<lpg-manage-permissions-dialog>` holding a `<p-dialog>`), so a wrapper
   * that contains one is walked into and only its other children are inerted;
   * inerting the wrapper would leave a dialog opened from the drawer visible
   * on top but impossible to click or type into.
   */
  private inertExceptOverlays(el: HTMLElement): void {
    if (el.matches(OVERLAY_SELECTOR) || el.hasAttribute('inert')) return;
    if (el.querySelector(OVERLAY_SELECTOR)) {
      for (const child of Array.from(el.children)) {
        if (child instanceof HTMLElement) this.inertExceptOverlays(child);
      }
      return;
    }
    el.setAttribute('inert', '');
    this.inerted.push(el);
  }

  private revert(): void {
    for (const el of this.inerted) el.removeAttribute('inert');
    this.inerted.length = 0;
  }
}
