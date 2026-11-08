import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Badge } from 'primeng/badge';
import { AuthTokenStore, PendingDevicesStore } from '@lpg/shared/data-access';
import { visibleSettingsGroups } from './settings-sections';

/**
 * Layout for everything under `/settings`: a row of section tabs above the
 * active section. Each section stays its own lazy child route, so deep links,
 * per-section permission guards and per-section page headers keep working —
 * this component only supplies the frame and hides sections the user cannot
 * open. Account (personal) and Agency (tenant-wide) are separate groups
 * because they differ in scope and in who may see them.
 */
@Component({
  selector: 'lpg-settings-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, Badge],
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
                    #link
                    routerLinkActive="is-active"
                    (isActiveChange)="onActiveChange($event, link)"
                    ariaCurrentWhenActive="page"
                    [routerLinkActiveOptions]="{ exact: section.exact ?? false }"
                  >
                    <i [class]="section.icon" aria-hidden="true"></i>
                    <span>{{ section.label }}</span>
                    @if (section.route === devicesRoute && pendingPhones() > 0) {
                      <p-badge
                        class="settings__badge"
                        [value]="pendingPhones()"
                        severity="danger"
                        [attr.aria-label]="pendingPhones() + ' phones waiting for approval'"
                      />
                    }
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
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        block-size: 100%;
        min-block-size: 0;
      }

      /* One row of tabs above the section. Account and Agency stay separate
         groups (a hairline divides them); the group captions remain for
         assistive technology but are not drawn. A row too wide for the screen
         scrolls sideways. */
      .settings__nav {
        display: flex;
        flex-direction: row;
        align-items: stretch;
        flex-shrink: 0;
        gap: var(--spacing-md);
        overflow-x: auto;
        border-block-end: 1px solid var(--color-border-default);
      }

      .settings__group {
        display: flex;
        flex-direction: row;
        flex-shrink: 0;
      }

      .settings__group + .settings__group {
        padding-inline-start: var(--spacing-md);
        border-inline-start: 1px solid var(--color-border-default);
      }

      .settings__group-label {
        position: absolute;
        margin: 0;
        padding: 0;
        inline-size: 1px;
        block-size: 1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
      }

      .settings__list {
        display: flex;
        flex-direction: row;
        gap: var(--spacing-xs);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .settings__link {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: 10px 12px;
        margin-block-end: -1px;
        border-block-end: 2px solid transparent;
        color: var(--color-text-secondary);
        text-decoration: none;
        white-space: nowrap;
        font-size: var(--typography-body-small-font-size);
        transition:
          border-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .settings__link:hover {
        color: var(--color-text-primary);
        border-block-end-color: var(--color-border-strong);
      }

      .settings__badge {
        margin-inline-start: var(--spacing-xs);
      }

      .settings__link:focus-visible {
        outline: 2px solid var(--color-border-focus);
        outline-offset: -2px;
      }

      .settings__link.is-active {
        color: var(--color-action-primary);
        border-block-end-color: var(--color-action-primary);
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
        padding-inline-end: var(--spacing-xl);
        /* Room for the 1px outline PrimeNG draws around p-message banners; the
           scroll container otherwise clips it along the top edge. */
        padding-block-start: var(--spacing-xs);
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
    `,
  ],
})
export class SettingsShell {
  private readonly tokenStore = inject(AuthTokenStore);
  private readonly pendingDevices = inject(PendingDevicesStore);

  /** Phones waiting for approval — shown next to Linked Devices. */
  protected readonly pendingPhones = this.pendingDevices.count;
  protected readonly devicesRoute = '/settings/license/devices';

  /**
   * Keeps the current tab in view when the row scrolls sideways (narrow
   * screens). Waits for the fonts and the next frame: the tabs change width as
   * the web font loads, so measuring earlier would scroll to the wrong place.
   */
  protected onActiveChange(active: boolean, link: HTMLElement): void {
    if (!active) return;
    const reveal = () =>
      requestAnimationFrame(() => link.scrollIntoView({ inline: 'nearest', block: 'nearest' }));
    if (typeof document !== 'undefined' && document.fonts) void document.fonts.ready.then(reveal);
    else reveal();
  }

  protected readonly groups = computed(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    return visibleSettingsGroups((code) => permissions?.has(code) ?? false);
  });
}
