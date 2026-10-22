import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthTokenStore } from '@lpg/shared/data-access';
import { visibleSettingsGroups } from './settings-sections';

/**
 * Layout for everything under `/settings`: a grouped section nav beside the
 * active section. Each section stays its own lazy child route, so deep links,
 * per-section permission guards and per-section page headers keep working —
 * this component only supplies the frame and hides sections the user cannot
 * open. Account (personal) and Agency (tenant-wide) are separate groups
 * because they differ in scope and in who may see them.
 */
@Component({
  selector: 'lpg-settings-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="settings">
      <nav class="settings__nav" aria-label="Settings sections">
        @for (group of groups(); track group.label) {
          <div class="settings__group">
            <h2 class="settings__group-label">{{ group.label }}</h2>
            <ul class="settings__list">
              @for (section of group.sections; track section.route) {
                <li>
                  <a
                    class="settings__link"
                    [routerLink]="section.route"
                    routerLinkActive="is-active"
                    ariaCurrentWhenActive="page"
                    [routerLinkActiveOptions]="{ exact: section.exact ?? false }"
                  >
                    <i [class]="section.icon" aria-hidden="true"></i>
                    <span>{{ section.label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
        }
      </nav>
      <div class="settings__content">
        <router-outlet />
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        flex: 1 1 0;
        min-block-size: 0;
        block-size: 100%;
        inline-size: 100%;
      }

      .settings {
        display: grid;
        grid-template-columns: 14rem minmax(0, 1fr);
        gap: var(--spacing-lg);
        align-items: stretch;
        block-size: 100%;
        min-block-size: 0;
      }

      .settings__nav {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        flex-shrink: 0;
        overflow-y: auto;
        min-block-size: 0;
      }

      .settings__group {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .settings__group-label {
        margin: 0;
        padding-inline: 12px;
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .settings__list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .settings__link {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: 8px 12px;
        border-radius: var(--radius-md);
        color: var(--color-text-secondary);
        text-decoration: none;
        white-space: nowrap;
        font-size: var(--typography-body-small-font-size);
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .settings__link:hover {
        background: var(--color-surface-overlay);
        color: var(--color-text-primary);
      }

      .settings__link:focus-visible {
        outline: 2px solid var(--color-border-focus);
        outline-offset: 2px;
      }

      .settings__link.is-active {
        background: var(--color-highlight-background);
        color: var(--color-highlight-color);
        font-weight: 600;
      }

      /* Settings sections sit flat on the page: drop the border and shadow of
         every card inside (hooks documented on SectionCardComponent).
         Only content scrolls inside settings, and content stretches to full width.
         The scrollbar sits flush at the extreme right edge (right: 0). */
      .settings__content {
        min-inline-size: 0;
        inline-size: 100%;
        block-size: 100%;
        min-block-size: 0;
        overflow-y: auto;
        padding-inline-start: var(--spacing-sm);
        padding-inline-end: var(--spacing-xl);
        padding-block-end: var(--spacing-xl);
        --card-border: none;
        --card-shadow: none;
      }

      .settings__content ::ng-deep > * {
        inline-size: 100%;
      }

      .settings__content ::ng-deep .admin-form-section,
      .settings__content ::ng-deep .admin-form-section form,
      .settings__content ::ng-deep .profile-card,
      .settings__content ::ng-deep .detail-view,
      .settings__content ::ng-deep .profile-page,
      .settings__content ::ng-deep .admin-page,
      .settings__content ::ng-deep .lpg-section-card {
        max-inline-size: none !important;
        inline-size: 100% !important;
      }

      /* Narrow screens: the nav becomes one horizontally scrolling row of
         links above the content; group captions are dropped to save space. */
      @media (max-width: 768px) {
        .settings {
          grid-template-columns: minmax(0, 1fr);
          gap: var(--spacing-md);
        }

        .settings__nav {
          flex-direction: row;
          gap: var(--spacing-sm);
          overflow-x: auto;
          padding-block-end: var(--spacing-xs);
        }

        .settings__group {
          flex-direction: row;
        }

        .settings__group-label {
          position: absolute;
          padding: 0;
          inline-size: 1px;
          block-size: 1px;
          overflow: hidden;
          clip-path: inset(50%);
        }

        .settings__list {
          flex-direction: row;
          gap: var(--spacing-xs);
        }
      }
    `,
  ],
})
export class SettingsShell {
  private readonly tokenStore = inject(AuthTokenStore);

  protected readonly groups = computed(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    return visibleSettingsGroups((code) => permissions?.has(code) ?? false);
  });
}
