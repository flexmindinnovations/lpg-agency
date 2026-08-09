import { ChangeDetectionStrategy, Component, computed, inject, input, model } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Menu } from 'primeng/menu';
import type { MenuItem } from 'primeng/api';
import { Badge } from 'primeng/badge';
import { Tooltip } from 'primeng/tooltip';
import { ThemeService, type ThemePreference } from '@lpg/shared/design-tokens';
import type { NavGroup } from './nav-item';

/**
 * Application shell: collapsible sidebar navigation, top bar, routed content.
 *
 * Data-driven and app-agnostic — `navGroups` is supplied by the consuming
 * app, never hardcoded here, so this component carries no assumption about
 * which business modules exist or what order they ship in (ADR-018's stated
 * goal of hosting a future second Angular app depends on that). The theme
 * switcher lives inside the shell itself (not the consuming app) because
 * every app that uses this shell needs one, in the same place, every time.
 */
@Component({
  selector: 'lpg-app-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, Menu, Badge, Tooltip],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a class="shell__skip-link" href="#shell-main-content">Skip to main content</a>

    <div class="shell" [class.shell--collapsed]="collapsed()">
      <header class="shell__top-bar">
        <button
          type="button"
          class="shell__collapse-toggle"
          [attr.aria-expanded]="!collapsed()"
          [attr.aria-label]="collapsed() ? 'Expand sidebar' : 'Collapse sidebar'"
          pTooltip="{{ collapsed() ? 'Expand' : 'Collapse' }} sidebar"
          tooltipPosition="bottom"
          (click)="collapsed.set(!collapsed())"
        >
          <i class="pi pi-bars" aria-hidden="true"></i>
        </button>

        <div class="shell__brand">
          <span class="shell__brand-mark" aria-hidden="true">{{ brandIcon() }}</span>
          @if (!collapsed()) {
            <span class="shell__brand-name">{{ brandName() }}</span>
          }
        </div>

        <div class="shell__top-bar-spacer"></div>
        <ng-content select="[shellActions]" />
      </header>

      <div class="shell__body">
        <nav class="shell__sidebar" aria-label="Main navigation">
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
                        [attr.aria-current]="rla.isActive ? 'page' : null"
                        [routerLinkActiveOptions]="{ exact: !!item.exact }"
                        class="shell__nav-link"
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

          <button
            type="button"
            class="shell__theme-trigger"
            [attr.aria-label]="'Theme: ' + themeLabel(themePreference())"
            (click)="themeMenu.toggle($event)"
          >
            <i [class]="themeIcon()" aria-hidden="true"></i>
            @if (!collapsed()) {
              <span class="shell__nav-label">{{ themeLabel(themePreference()) }}</span>
            }
          </button>
          <p-menu #themeMenu [model]="themeMenuItems()" [popup]="true" appendTo="body" />
        </nav>

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
      }
      .shell__skip-link:focus {
        inset-inline-start: var(--spacing-sm);
        inset-block-start: var(--spacing-sm);
      }

      .shell {
        display: flex;
        flex-direction: column;
        block-size: 100vh;
      }

      .shell__top-bar {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        block-size: var(--component-app-shell-top-bar-height);
        padding-inline: var(--spacing-md);
        background: var(--color-surface-raised);
        border-block-end: var(--border-width) solid var(--color-border-default);
        flex-shrink: 0;
      }

      .shell__collapse-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 2rem;
        block-size: 2rem;
        border: none;
        background: transparent;
        color: var(--color-text-secondary);
        border-radius: var(--radius-sm);
        cursor: pointer;
        font-size: var(--typography-body-font-size);
      }
      .shell__collapse-toggle:hover {
        background: var(--color-surface-overlay);
      }

      .shell__brand {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        overflow: hidden;
      }
      .shell__brand-mark {
        color: var(--color-action-primary);
        font-size: var(--typography-heading2-font-size);
        flex-shrink: 0;
      }
      .shell__brand-name {
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading2-font-weight);
        white-space: nowrap;
      }

      .shell__top-bar-spacer {
        flex: 1;
      }

      .shell__body {
        display: flex;
        flex: 1;
        min-block-size: 0;
      }

      .shell__sidebar {
        display: flex;
        flex-direction: column;
        inline-size: var(--component-app-shell-sidebar-width);
        flex-shrink: 0;
        padding: var(--spacing-md);
        background: var(--color-surface-raised);
        border-inline-end: var(--border-width) solid var(--color-border-default);
        overflow-y: auto;
        overflow-x: hidden;
        transition: inline-size var(--motion-duration-small) var(--motion-easing-standard);
      }
      .shell--collapsed .shell__sidebar {
        inline-size: var(--component-app-shell-sidebar-collapsed-width);
      }

      .shell__nav-groups {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        flex: 1;
      }
      .shell__nav-group-label {
        margin: 0 0 var(--spacing-xs);
        padding-inline: var(--spacing-sm);
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .shell__nav-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }
      .shell__nav-link {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-sm);
        border-radius: var(--radius-sm);
        color: var(--color-text-primary);
        text-decoration: none;
        white-space: nowrap;
        overflow: hidden;
      }
      .shell__nav-link i {
        font-size: var(--typography-body-font-size);
        flex-shrink: 0;
        inline-size: 1.25rem;
        text-align: center;
      }
      .shell__nav-link:hover {
        background: var(--color-surface-overlay);
      }
      .shell__nav-link.is-active {
        background: var(--color-highlight-background);
        color: var(--color-highlight-color);
        font-weight: var(--typography-label-font-weight);
      }
      .shell__nav-label {
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .shell__theme-trigger {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        inline-size: 100%;
        margin-block-start: var(--spacing-md);
        padding: var(--spacing-sm);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-sm);
        background: var(--color-surface-base);
        color: var(--color-text-primary);
        cursor: pointer;
        font-size: var(--typography-body-small-font-size);
        white-space: nowrap;
        overflow: hidden;
      }
      .shell__theme-trigger:hover {
        background: var(--color-surface-overlay);
      }

      .shell__main {
        flex: 1;
        padding: var(--spacing-xl);
        overflow-y: auto;
      }
      .shell__main:focus {
        outline: none;
      }
    `,
  ],
})
export class AppShellComponent {
  readonly brandName = input('');
  readonly brandIcon = input('◆');
  readonly navGroups = input.required<readonly NavGroup[]>();
  readonly collapsed = model(false);

  private readonly themeService = inject(ThemeService);
  protected readonly themePreference = this.themeService.preference;

  private static readonly THEME_ICONS: Record<ThemePreference, string> = {
    system: 'pi pi-desktop',
    light: 'pi pi-sun',
    dark: 'pi pi-moon',
    'high-contrast': 'pi pi-eye',
  };

  protected readonly themeIcon = computed(
    () => AppShellComponent.THEME_ICONS[this.themePreference()],
  );

  protected readonly themeMenuItems = computed<MenuItem[]>(() => {
    const current = this.themePreference();
    const options: readonly ThemePreference[] = ['system', ...this.themeService.availableThemes];
    return options.map((option) => ({
      label: this.themeLabel(option),
      icon: AppShellComponent.THEME_ICONS[option],
      styleClass: option === current ? 'is-selected-theme' : undefined,
      command: () => this.themeService.setPreference(option),
    }));
  });

  protected themeLabel(preference: ThemePreference): string {
    return preference === 'high-contrast'
      ? 'High contrast'
      : preference.charAt(0).toUpperCase() + preference.slice(1);
  }
}
