import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  model,
  output,
  signal,
  untracked,
} from '@angular/core';
import { BreakpointObserver } from '@angular/cdk/layout';
import {
  Router,
  RouterLink,
  RouterLinkActive,
  NavigationEnd,
  ActivatedRoute,
} from '@angular/router';
import { Badge } from 'primeng/badge';
import { Tooltip } from 'primeng/tooltip';
import { Breadcrumb } from 'primeng/breadcrumb';
import type { MenuItem } from 'primeng/api';
import type { NavGroup, NavItem } from './nav-item';
import { ProfileMenuComponent } from '../profile-menu/profile-menu.component';
import { PortalModule } from '@angular/cdk/portal';
import { HeaderPortalService } from './header-portal.service';
import { BreadcrumbService } from './breadcrumb.service';
import { filter } from 'rxjs/operators';
import { map } from 'rxjs/operators';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';

/** Below this the sidebar is an off-canvas menu behind a header button. */
const PHONE_QUERY = '(max-width: 767.98px)';
/** Below this (tablet) the sidebar starts as the icon rail, so grids get the width. */
const COMPACT_QUERY = '(max-width: 1199.98px)';

@Component({
  selector: 'lpg-app-shell',
  standalone: true,
  imports: [
    RouterLink,
    RouterLinkActive,
    Badge,
    Tooltip,
    ProfileMenuComponent,
    PortalModule,
    Breadcrumb,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  // Escape closes the phone menu (a no-op when it is not open).
  host: { '(document:keydown.escape)': 'closeNav(true)' },
  template: `
    <a class="shell__skip-link" href="#shell-main-content">Skip to main content</a>

    <div
      class="shell"
      [class.shell--collapsed]="rail()"
      [class.shell--phone]="isPhone()"
      [class.shell--nav-open]="isPhone() && navOpen()"
    >
      @if (isPhone() && navOpen()) {
        <!-- Tap-outside target; keyboard users close with Escape or "Close menu". -->
        <button
          type="button"
          class="shell__backdrop"
          tabindex="-1"
          aria-label="Close menu"
          (click)="closeNav()"
        ></button>
      }
      <div
        id="shell-sidebar"
        class="shell__sidebar-wrapper"
        [attr.inert]="isPhone() && !navOpen() ? '' : null"
      >
        <nav class="shell__sidebar" aria-label="Main navigation">
          <!-- Brand -->
          <div class="shell__sidebar-header">
            <div class="shell__brand">
              <svg class="shell__brand-mark" viewBox="0 0 24 24" aria-hidden="true">
                <!-- Outer Flame -->
                <path
                  d="M12 2C15 5 19 9 19 14.5C19 18.64 15.86 22 12 22C8.14 22 5 18.64 5 14.5C5 9 9 5 12 2Z"
                  fill="currentColor"
                />
                <!-- Inner Flame -->
                <path
                  d="M12 10C13.5 12 15 13.5 15 15.5C15 17.43 13.66 19 12 19C10.34 19 9 17.43 9 15.5C9 13.5 10.5 12 12 10Z"
                  fill="var(--primitive-color-flame-orange-500, #ff6f12)"
                />
              </svg>
              @if (!rail()) {
                <span class="shell__brand-name">{{ brandName() }}</span>
              }
            </div>
          </div>

          <!-- Navigation Groups -->
          <ul class="shell__nav-groups">
            @for (group of navGroups(); track group.label ?? $index) {
              <li>
                @if (group.label && !rail()) {
                  <p class="shell__nav-group-label">{{ group.label }}</p>
                }
                <ul class="shell__nav-list">
                  @for (item of group.items; track item.route) {
                    <li>
                      <a
                        [routerLink]="item.route"
                        routerLinkActive="is-active"
                        #rla="routerLinkActive"
                        [attr.aria-current]="
                          rla.isActive || isAliasActive(item, router.url) ? 'page' : null
                        "
                        [routerLinkActiveOptions]="{ exact: !!item.exact }"
                        class="shell__nav-link"
                        [class.is-active]="rla.isActive || isAliasActive(item, router.url)"
                        pTooltip="{{ rail() ? item.label : '' }}"
                        tooltipPosition="right"
                        [attr.aria-label]="rail() ? item.label : null"
                      >
                        <i class="{{ item.icon }}" aria-hidden="true"></i>
                        @if (!rail()) {
                          <span class="shell__nav-label">{{ item.label }}</span>
                        }
                        @if (item.badge && !rail()) {
                          <p-badge [value]="item.badge" severity="danger" />
                        }
                      </a>
                    </li>
                  }
                </ul>
              </li>
            }
          </ul>

          <!-- Profile Menu in Sidebar Footer -->
          <div class="shell__sidebar-footer">
            <lpg-profile-menu
              class="shell__sidebar-profile"
              [email]="email()"
              [role]="role()"
              [collapsed]="rail()"
              (signOut)="signOut.emit()"
            />
          </div>
        </nav>

        @if (isPhone()) {
          <button
            type="button"
            class="shell__nav-close"
            aria-label="Close menu"
            (click)="closeNav(true)"
          >
            <i class="pi pi-times" aria-hidden="true"></i>
          </button>
        }
        <button
          type="button"
          class="shell__collapse-toggle"
          [attr.aria-expanded]="!rail()"
          [attr.aria-label]="rail() ? 'Expand sidebar' : 'Collapse sidebar'"
          pTooltip="{{ rail() ? 'Expand' : 'Collapse' }} sidebar"
          [tooltipPosition]="rail() ? 'right' : 'bottom'"
          (click)="collapsed.set(!rail())"
        >
          <i
            class="pi"
            [class.pi-chevron-left]="!rail()"
            [class.pi-chevron-right]="rail()"
            aria-hidden="true"
          ></i>
        </button>
      </div>

      <div class="shell__content">
        <header class="shell__header">
          <button
            type="button"
            class="shell__menu-button"
            aria-controls="shell-sidebar"
            [attr.aria-expanded]="navOpen()"
            aria-label="Open menu"
            (click)="openNav()"
          >
            <i class="pi pi-bars" aria-hidden="true"></i>
          </button>
          <div class="shell__header-spacer">
            <ng-template [cdkPortalOutlet]="headerPortalService.titlePortal()"></ng-template>
          </div>
          <div class="shell__header-actions">
            <!-- Page-specific actions render left of the always-present
                 notification bell, which stays pinned to the far right. -->
            <ng-template [cdkPortalOutlet]="headerPortalService.portal()"></ng-template>
            <ng-content select="[shell-top-right-actions]" />
          </div>
        </header>

        @if (breadcrumbService.items().length > 0 || headerPortalService.actionsPortal()) {
          <div class="shell__breadcrumb-wrapper">
            @if (breadcrumbService.items().length > 0) {
              <p-breadcrumb
                [model]="breadcrumbService.items()"
                [home]="breadcrumbService.home()"
                homeAriaLabel="Home"
                styleClass="shell__breadcrumb"
              />
            }
            <!-- The page's own actions, right-aligned on the breadcrumb row
                 (lpgPageActions) — the same place on every page. -->
            <div class="shell__page-actions">
              <ng-template [cdkPortalOutlet]="headerPortalService.actionsPortal()"></ng-template>
            </div>
          </div>
        }

        <main id="shell-main-content" class="shell__main" tabindex="-1">
          <ng-content />
        </main>
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .shell__skip-link {
        position: absolute;
        inset-inline-start: -9999px;
        z-index: var(--z-index-tooltip);
        padding: var(--spacing-sm) var(--spacing-md);
        background: var(--color-action-primary);
        color: var(--color-action-primary-text);
        border-radius: var(--radius-md);
        text-decoration: none;
        font-weight: var(--typography-label-font-weight);
        font-size: var(--typography-body-small-font-size);
      }
      .shell__skip-link:focus {
        inset-inline-start: var(--spacing-sm);
        inset-block-start: var(--spacing-sm);
      }

      /* ---- Layout ---- */

      .shell {
        display: flex;
        block-size: 100vh;
      }

      /* ---- Sidebar Wrapper & Sidebar ---- */

      /* Persistent chrome — a solid surface one step up from the page ground,
         separated by a single border. */
      .shell__sidebar-wrapper {
        position: relative;
        display: flex;
        flex-direction: column;
        inline-size: var(--component-app-shell-sidebar-width);
        flex-shrink: 0;
        background: var(--surface-mica);
        border-inline-end: var(--border-width) solid var(--surface-mica-border);
        transition: inline-size var(--motion-duration-medium) var(--motion-easing-emphasized);
        z-index: 10;
      }

      .shell--collapsed .shell__sidebar-wrapper {
        inline-size: var(--component-app-shell-sidebar-collapsed-width);
      }

      .shell__sidebar {
        display: flex;
        flex-direction: column;
        block-size: 100%;
        overflow: hidden;
      }

      /* ---- Sidebar Header (brand only) ---- */

      .shell__sidebar-header {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: var(--spacing-md);
        padding-block-end: var(--spacing-md);
        flex-shrink: 0;
        block-size: 64px;
        /* The nav list scrolls beneath this header; a divider makes the
           boundary explicit so a half-scrolled item never reads as sitting
           under the logo (QA UR-02). */
        border-block-end: var(--border-width) solid var(--surface-mica-border);
      }

      .shell--collapsed .shell__sidebar-header {
        justify-content: center;
      }

      .shell__brand {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        overflow: hidden;
        min-inline-size: 0;
      }

      .shell__brand-mark {
        inline-size: var(--icon-size-xl);
        block-size: var(--icon-size-xl);
        flex-shrink: 0;
        /* The brand mark keeps its own flame identity regardless of the
           palette (Phase 29 decision) — not tied to --color-action-primary,
           which is now blue. */
        color: var(--primitive-color-flame-orange-500);
      }

      .shell__brand-name {
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.02em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--color-text-primary);
      }

      /* ---- Floating Collapse Toggle ---- */

      .shell__collapse-toggle {
        position: absolute;
        inset-inline-end: -12px;
        inset-block-start: 20px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 24px;
        block-size: 24px;
        border: var(--border-width) solid var(--color-border-strong);
        background: var(--color-surface-overlay);
        color: var(--color-text-secondary);
        border-radius: 50%;
        cursor: pointer;
        z-index: 20;
        box-shadow: var(--elevation-1);
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard),
          border-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .shell__collapse-toggle:hover {
        background: var(--color-surface-overlay);
        color: var(--color-text-primary);
        border-color: var(--color-border-strong);
      }

      /* ---- Sidebar Footer ---- */

      .shell__sidebar-footer {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border-block-start: var(--border-width) solid var(--color-border-default);
      }

      .shell--collapsed .shell__sidebar-footer {
        flex-direction: column;
      }

      .shell__sidebar-profile {
        flex: 1;
        min-inline-size: 0;
      }

      .shell__collapse-toggle i {
        font-size: 10px;
      }

      /* ---- Navigation ---- */

      .shell__nav-groups {
        list-style: none;
        margin: 0;
        padding: 0 var(--spacing-sm) var(--spacing-md);
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        flex: 1;
        /* Without this, a flex:1 column item won't shrink below its content
           size, so overflow-y:auto below would never actually kick in —
           the item would just grow and push the sidebar itself to overflow
           instead of scrolling internally. */
        min-block-size: 0;
        overflow-y: auto;
        overflow-x: hidden;
        padding-block-start: var(--spacing-md);
        scroll-padding-block: var(--spacing-md);
        overscroll-behavior: contain;
      }

      .shell--collapsed .shell__nav-groups {
        padding: var(--spacing-sm) var(--spacing-xs) var(--spacing-xs);
        align-items: center;
      }

      .shell__nav-group-label {
        margin: 0 0 var(--spacing-xs);
        padding-inline: var(--spacing-sm);
        font-size: 11px;
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        /* Full secondary colour, no opacity: at 0.7 the labels were 2.66:1
           (light) and 3.16:1 (dark) — QA DA-23/DO-35. */
      }

      .shell__nav-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 1px;
      }

      .shell__nav-link {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: 8px 12px;
        border-radius: var(--radius-md);
        color: var(--color-text-secondary);
        text-decoration: none;
        white-space: nowrap;
        overflow: hidden;
        font-size: var(--typography-body-small-font-size);
        font-weight: 400;
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
        position: relative;
      }

      .shell__nav-link i {
        font-size: var(--icon-size-md); /* 18px — doc §12 nav icon size */
        flex-shrink: 0;
        inline-size: 1.5rem;
        text-align: center;
        opacity: 0.7;
        transition: opacity var(--motion-duration-small) var(--motion-easing-standard);
      }

      .shell__nav-link:focus-visible,
      .shell__collapse-toggle:focus-visible,
      .shell__menu-button:focus-visible,
      .shell__nav-close:focus-visible {
        outline: var(--component-focus-ring-width) solid var(--component-focus-ring-color);
        outline-offset: calc(-1 * var(--component-focus-ring-width));
      }

      .shell__nav-link:hover {
        background: var(--color-surface-overlay);
        color: var(--color-text-primary);
      }

      .shell__nav-link:hover i {
        opacity: 1;
      }

      /* Active item: the themed highlight surface + its paired text colour
         (a subtle blue tint in dark, per doc §13), medium weight — no glow,
         no heavy 700 weight. Text/icon stay on --color-highlight-color so
         this reads correctly in light + high-contrast too. */
      .shell__nav-link.is-active {
        background: var(--color-highlight-background);
        color: var(--color-highlight-color);
        font-weight: 600;
      }

      .shell__nav-link.is-active i {
        opacity: 1;
      }

      .shell__nav-label {
        overflow: hidden;
        text-overflow: ellipsis;
      }

      /* ---- Collapsed nav ---- */

      .shell--collapsed .shell__nav-link {
        justify-content: center;
        padding: 10px;
      }

      .shell--collapsed .shell__nav-link i {
        inline-size: auto;
      }

      /* ---- Main Content ---- */

      /* Flat solid base — the page ground. */
      .shell__content {
        position: relative;
        display: flex;
        flex-direction: column;
        flex: 1;
        min-inline-size: 0;
        background: var(--color-surface-base);
      }

      /* ---- Global Header ---- (solid chrome, same surface as the sidebar) */
      .shell__header {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        min-block-size: 64px;
        padding: var(--spacing-xs) var(--spacing-xl);
        border-block-end: var(--border-width) solid var(--surface-mica-border);
        background: var(--surface-mica);
        flex-shrink: 0;
        gap: var(--spacing-md);
      }

      /* Transparent — the breadcrumb belongs to the content column, not the
         header chrome. */
      .shell__breadcrumb-wrapper {
        display: flex;
        align-items: center;
        flex-wrap: nowrap;
        gap: var(--spacing-sm) var(--spacing-md);
        min-block-size: calc(var(--component-action-height) + 2 * var(--spacing-sm));
        padding: var(--spacing-sm) var(--spacing-xl);
        background: transparent;
      }

      /* The content starts close under the breadcrumb row. */
      .shell__breadcrumb-wrapper + .shell__main {
        padding-block-start: var(--spacing-sm);
      }

      .shell__page-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        flex-wrap: nowrap;
        overflow-x: auto;
        scrollbar-width: none;
        gap: var(--spacing-xs);
        margin-inline-start: auto;
        min-inline-size: 0;
        flex: 1 1 auto;
      }

      .shell__page-actions::-webkit-scrollbar {
        display: none;
      }

      .shell__page-actions:empty {
        display: none;
      }

      :host ::ng-deep .shell__page-actions .p-button {
        white-space: nowrap;
        flex-shrink: 0;
      }

      :host ::ng-deep .shell__breadcrumb {
        flex: 0 0 auto;
        min-inline-size: 0;
        padding: 0;
        background: transparent;
        border: none;
        margin-block-end: 0;
        font-size: var(--typography-body-small-font-size);
        /* PrimeNG renders this <nav> with overflow:auto, which clips the
           focus ring on the home icon and every breadcrumb link — a single
           line of text/icons never needs to scroll internally, so this is
           safe. */
        overflow: visible;
      }
      :host ::ng-deep .shell__breadcrumb .p-breadcrumb-list li a {
        text-decoration: none;
      }
      :host ::ng-deep .shell__breadcrumb .p-breadcrumb-list li a:focus-visible {
        outline: 2px solid var(--color-border-focus);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
      }

      /* Holds the portalled page title; min-inline-size:0 lets its one-line
         title/subtitle shrink to an ellipsis instead of wrapping into the
         header actions. */
      .shell__header-spacer {
        flex: 1;
        min-inline-size: 0;
      }

      .shell__header-actions {
        flex-shrink: 0;
      }

      .shell__header-actions {
        display: flex;
        gap: var(--spacing-sm);
        align-items: center;
      }

      .shell__main {
        position: relative;
        flex: 1;
        min-inline-size: 0;
        padding: var(--spacing-lg) var(--spacing-xl);
        overflow-x: hidden;
        overflow-y: auto;
        /* Transparent — the atmospheric base on .shell__content shows through. */
        background: transparent;
      }

      .shell__main:focus,
      .shell__main:focus-visible {
        outline: none;
      }

      /* ---- Phone: off-canvas sidebar (QA DA-20, DO-36) ---- */

      /* The menu button only exists in the phone layout. */
      .shell__menu-button,
      .shell__nav-close {
        display: none;
        align-items: center;
        justify-content: center;
        inline-size: var(--spacing-xl);
        block-size: var(--spacing-xl);
        padding: 0;
        border: var(--border-width) solid transparent;
        border-radius: var(--radius-md);
        background: transparent;
        color: var(--color-text-primary);
        cursor: pointer;
      }

      .shell__menu-button:hover,
      .shell__nav-close:hover {
        background: var(--color-surface-overlay);
      }

      .shell__menu-button i,
      .shell__nav-close i {
        font-size: var(--icon-size-md);
      }

      .shell--phone .shell__menu-button {
        display: inline-flex;
        flex-shrink: 0;
        margin-inline-end: var(--spacing-sm);
      }

      .shell--phone .shell__nav-close {
        display: inline-flex;
        position: absolute;
        inset-block-start: var(--spacing-md);
        inset-inline-end: var(--spacing-sm);
      }

      .shell--phone .shell__collapse-toggle {
        display: none;
      }

      /* Closed by default: off screen, hidden from the tab order (and
         \`inert\` from the template) until the menu button opens it. The
         content column gets the full width. */
      .shell--phone .shell__sidebar-wrapper {
        position: fixed;
        inset-block: 0;
        inset-inline-start: 0;
        inline-size: min(var(--component-app-shell-sidebar-width), 85vw);
        z-index: var(--z-index-drawer);
        transform: translateX(-100%);
        visibility: hidden;
        transition:
          transform var(--motion-duration-medium) var(--motion-easing-emphasized),
          visibility 0s linear var(--motion-duration-medium);
      }

      .shell--phone.shell--nav-open .shell__sidebar-wrapper {
        transform: none;
        visibility: visible;
        box-shadow: var(--elevation-4);
        transition: transform var(--motion-duration-medium) var(--motion-easing-emphasized);
      }

      .shell__backdrop {
        position: fixed;
        inset: 0;
        padding: 0;
        border: 0;
        cursor: default;
        z-index: calc(var(--z-index-drawer) - 1);
        background: color-mix(in srgb, var(--color-surface-base), black 55%);
        opacity: 0.6;
      }

      .shell--phone .shell__header {
        flex-wrap: nowrap;
        padding: var(--spacing-sm) var(--spacing-md);
      }

      .shell--phone .shell__breadcrumb-wrapper {
        padding-inline: var(--spacing-md);
      }

      .shell--phone .shell__main {
        padding: var(--spacing-md);
      }

      /* Tablet: tighter gutters so grids keep their key columns (DA-21). */
      @media (max-width: 1199.98px) {
        .shell__header,
        .shell__breadcrumb-wrapper {
          padding-inline: var(--spacing-lg);
        }

        .shell__main {
          padding-inline: var(--spacing-lg);
        }
      }
    `,
  ],
})
export class AppShellComponent {
  protected readonly router = inject(Router);
  protected readonly headerPortalService = inject(HeaderPortalService);
  protected readonly breadcrumbService = inject(BreadcrumbService);
  private readonly activatedRoute = inject(ActivatedRoute);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly breakpoints = inject(BreakpointObserver);

  readonly brandName = input('');
  /** Overrides the default brand mark with a PrimeIcon class or literal glyph. */
  readonly brandIcon = input<string | null>(null);
  readonly navGroups = input.required<readonly NavGroup[]>();
  readonly email = input<string | null>(null);
  readonly role = input<string>('');

  readonly collapsed = model(false);

  /** Phone width: the sidebar is an off-canvas menu (closed by default). */
  protected readonly isPhone = toSignal(
    this.breakpoints.observe(PHONE_QUERY).pipe(map((state) => state.matches)),
    { initialValue: false },
  );
  private readonly isCompact = toSignal(
    this.breakpoints.observe(COMPACT_QUERY).pipe(map((state) => state.matches)),
    { initialValue: false },
  );
  /** Whether the phone menu is open. Ignored at tablet/desktop widths. */
  readonly navOpen = signal(false);
  /** The icon-only rail: collapsed, and never in the phone menu (which shows labels). */
  protected readonly rail = computed(() => !this.isPhone() && this.collapsed());

  readonly signOut = output<void>();
  readonly notificationToggle = output<void>();

  constructor() {
    // Tablet and narrower start on the icon rail and desktop on the full
    // sidebar; crossing the breakpoint resets it. The user's toggle still
    // wins until the next crossing.
    effect(() => {
      const compact = this.isCompact();
      untracked(() => this.collapsed.set(compact));
    });
    effect(() => {
      if (!this.isPhone()) untracked(() => this.navOpen.set(false));
    });

    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        let route = this.activatedRoute.root;
        let breadcrumbs: MenuItem[] = [];

        // Traverse the active route tree to collect breadcrumbs from data
        while (route.firstChild) {
          route = route.firstChild;
          if (route.snapshot.data['breadcrumbs']) {
            breadcrumbs = route.snapshot.data['breadcrumbs'];
          }
        }

        this.navOpen.set(false);
        this.revealActiveLink();

        if (breadcrumbs.length > 0) {
          this.breadcrumbService.setItems(breadcrumbs);
        } else {
          this.breadcrumbService.clear();
        }
      });
  }

  protected openNav(): void {
    this.navOpen.set(true);
    // Focus the first link once the menu is visible.
    requestAnimationFrame(() =>
      this.host.nativeElement.querySelector<HTMLElement>('.shell__nav-link')?.focus(),
    );
  }

  /** Close the phone menu; `returnFocus` puts focus back on the menu button. */
  protected closeNav(returnFocus = false): void {
    if (!this.navOpen()) return;
    this.navOpen.set(false);
    if (returnFocus) {
      this.host.nativeElement.querySelector<HTMLElement>('.shell__menu-button')?.focus();
    }
  }

  /** Keep the current page's nav item scrolled into view in a long sidebar. */
  private revealActiveLink(): void {
    if (typeof requestAnimationFrame !== 'function') return;
    requestAnimationFrame(() => {
      const container = this.host.nativeElement.querySelector<HTMLElement>('.shell__nav-groups');
      const active = this.host.nativeElement.querySelector<HTMLElement>(
        '.shell__nav-link.is-active',
      );
      if (!container || !active) return;
      const cRect = container.getBoundingClientRect();
      const aRect = active.getBoundingClientRect();
      // Only scroll if the active item is currently outside the visible sidebar viewport
      if (aRect.top < cRect.top || aRect.bottom > cRect.bottom) {
        active.scrollIntoView?.({ block: 'nearest' });
      }
    });
  }

  protected isAliasActive(item: NavItem, currentUrl: string): boolean {
    if (!item.aliases) return false;
    return item.aliases.some((alias) => currentUrl.startsWith(alias));
  }
}
