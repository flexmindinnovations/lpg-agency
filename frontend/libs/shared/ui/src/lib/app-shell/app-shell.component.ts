import { ChangeDetectionStrategy, Component, inject, input, model, output } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { Badge } from 'primeng/badge';
import { Tooltip } from 'primeng/tooltip';
import { Breadcrumb } from 'primeng/breadcrumb';
import type { NavGroup, NavItem } from './nav-item';
import { ProfileMenuComponent } from '../profile-menu/profile-menu.component';
import { PortalModule } from '@angular/cdk/portal';
import { HeaderPortalService } from './header-portal.service';
import { BreadcrumbService } from './breadcrumb.service';
/**
 * Application shell: collapsible sidebar navigation with integrated brand,
 * and a full-height routed content area.
 *
 * The top-bar was removed during the Premium UI redesign — the brand now lives
 * in the sidebar header (matching Linear, Notion, Arc's pattern), and the
 * sidebar/main-content split uses the full viewport height. The sidebar
 * collapse toggle moved into the sidebar header alongside the brand.
 *
 * Data-driven and app-agnostic — `navGroups` is supplied by the consuming
 * app, never hardcoded here, so this component carries no assumption about
 * which business modules exist or what order they ship in (ADR-018's stated
 * goal of hosting a future second Angular app depends on that).
 */
@Component({
  selector: 'lpg-app-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, Badge, Tooltip, ProfileMenuComponent, PortalModule, Breadcrumb],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a class="shell__skip-link" href="#shell-main-content">Skip to main content</a>

    <div class="shell" [class.shell--collapsed]="collapsed()">
      <div class="shell__sidebar-wrapper">
        <nav class="shell__sidebar" aria-label="Main navigation">
          <!-- Brand -->
          <div class="shell__sidebar-header">
            <div class="shell__brand">
              <svg
                class="shell__brand-mark"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
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
              @if (!collapsed()) {
                <span class="shell__brand-name">{{ brandName() }}</span>
              }
            </div>
          </div>

          <!-- Navigation Groups -->
          <ul class="shell__nav-groups">
            @for (group of navGroups(); track group.label ?? $index) {
              <li>
                @if (group.label && !collapsed()) {
                  <p class="shell__nav-group-label">{{ group.label }}</p>
                }
                <ul class="shell__nav-list">
                  @for (item of group.items; track item.route) {
                    <li>
                      <a
                        [routerLink]="item.route"
                        routerLinkActive="is-active"
                        #rla="routerLinkActive"
                        [attr.aria-current]="(rla.isActive || isAliasActive(item, router.url)) ? 'page' : null"
                        [routerLinkActiveOptions]="{ exact: !!item.exact }"
                        class="shell__nav-link"
                        [class.is-active]="rla.isActive || isAliasActive(item, router.url)"
                        pTooltip="{{ collapsed() ? item.label : '' }}"
                        tooltipPosition="right"
                        [attr.aria-label]="collapsed() ? item.label : null"
                      >
                        <i class="{{ item.icon }}" aria-hidden="true"></i>
                        @if (!collapsed()) {
                          <span class="shell__nav-label">{{ item.label }}</span>
                        }
                        @if (item.badge && !collapsed()) {
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
              [collapsed]="collapsed()"
              (signOut)="signOut.emit()"
            />
          </div>
        </nav>

        <button
          type="button"
          class="shell__collapse-toggle"
          [attr.aria-expanded]="!collapsed()"
          [attr.aria-label]="collapsed() ? 'Expand sidebar' : 'Collapse sidebar'"
          pTooltip="{{ collapsed() ? 'Expand' : 'Collapse' }} sidebar"
          [tooltipPosition]="collapsed() ? 'right' : 'bottom'"
          (click)="collapsed.set(!collapsed())"
        >
          <i
            class="pi"
            [class.pi-chevron-left]="!collapsed()"
            [class.pi-chevron-right]="collapsed()"
            aria-hidden="true"
          ></i>
        </button>
      </div>

      <div class="shell__content">
        <header class="shell__header">
          @if (breadcrumbService.items().length > 0) {
            <p-breadcrumb
              [model]="breadcrumbService.items()"
              [home]="breadcrumbService.home()"
              styleClass="shell__breadcrumb"
            />
          }
          <div class="shell__header-spacer">
            <ng-template [cdkPortalOutlet]="headerPortalService.titlePortal()"></ng-template>
          </div>
          <div class="shell__header-actions">
            <ng-content select="[shell-top-right-actions]" />
            <ng-template [cdkPortalOutlet]="headerPortalService.portal()"></ng-template>
          </div>
        </header>

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

      .shell__sidebar-wrapper {
        position: relative;
        display: flex;
        flex-direction: column;
        inline-size: var(--component-app-shell-sidebar-width);
        flex-shrink: 0;
        background: var(--color-surface-base);
        border-inline-end: var(--border-width) solid var(--color-border-default);
        transition: inline-size var(--motion-duration-medium) var(--motion-easing-standard);
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
        inline-size: 1.5rem;
        block-size: 1.5rem;
        flex-shrink: 0;
        color: var(--color-action-primary);
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
        border: var(--border-width) solid var(--color-border-default);
        background: var(--color-surface-base);
        color: var(--color-text-secondary);
        border-radius: 50%;
        cursor: pointer;
        z-index: 20;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: background-color var(--motion-duration-small) var(--motion-easing-standard),
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
      }

      .shell--collapsed .shell__nav-groups {
        padding: 0 var(--spacing-xs) var(--spacing-xs);
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
        opacity: 0.7;
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
        transition: background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
        position: relative;
      }

      .shell__nav-link i {
        font-size: 18px; /* Increased nav icon size */
        flex-shrink: 0;
        inline-size: 1.5rem;
        text-align: center;
        opacity: 0.7;
        transition: opacity var(--motion-duration-small) var(--motion-easing-standard);
      }

      .shell__nav-link:hover {
        background: var(--color-surface-overlay);
        color: var(--color-text-primary);
      }

      .shell__nav-link:hover i {
        opacity: 1;
      }

      .shell__nav-link.is-active {
        background: var(--color-highlight-background);
        color: var(--color-highlight-color);
        font-weight: 700;
      }

      .shell__nav-link.is-active i {
        opacity: 1;
        font-weight: 700;
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

      .shell__content {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-inline-size: 0;
      }

      /* ---- Global Header ---- */
      .shell__header {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        min-block-size: 72px;
        padding: 8px var(--spacing-xl);
        border-block-end: var(--border-width) solid var(--color-border-default);
        background: var(--color-surface-base);
        flex-shrink: 0;
        flex-wrap: wrap;
      }
      
      :host ::ng-deep .shell__breadcrumb {
        width: 100%;
        padding: 0;
        background: transparent;
        border: none;
        margin-block-end: var(--spacing-xs);
        font-size: var(--typography-body-small-font-size);
      }
      :host ::ng-deep .shell__breadcrumb .p-breadcrumb-list li a {
        text-decoration: none;
      }
      :host ::ng-deep .shell__breadcrumb .p-breadcrumb-list li a:focus-visible {
        outline: 2px solid var(--color-focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
      }

      .shell__header-spacer {
        flex: 1;
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
        background: var(--color-surface-base);
      }

      .shell__main:focus,
      .shell__main:focus-visible {
        outline: none;
      }

      /* ---- Responsive ---- */

      @media (max-width: 768px) {
        .shell__sidebar-wrapper {
          inline-size: var(--component-app-shell-sidebar-collapsed-width);
        }

        .shell__sidebar-header {
          justify-content: center;
        }

        .shell__nav-groups {
          padding: 0 var(--spacing-xs) var(--spacing-xs);
          align-items: center;
        }

        .shell__nav-link {
          justify-content: center;
          padding: 10px;
        }

        .shell__main {
          padding: var(--spacing-md);
        }
      }
    `,
  ],
})
export class AppShellComponent {
  protected readonly router = inject(Router);
  protected readonly headerPortalService = inject(HeaderPortalService);
  protected readonly breadcrumbService = inject(BreadcrumbService);

  readonly brandName = input('');
  /** Overrides the default brand mark with a PrimeIcon class or literal glyph. */
  readonly brandIcon = input<string | null>(null);
  readonly navGroups = input.required<readonly NavGroup[]>();
  readonly email = input<string | null>(null);
  readonly role = input<string>('');

  readonly collapsed = model(false);

  readonly signOut = output<void>();
  readonly notificationToggle = output<void>();

  protected isAliasActive(item: NavItem, currentUrl: string): boolean {
    if (!item.aliases) return false;
    return item.aliases.some(alias => currentUrl.startsWith(alias));
  }
}
