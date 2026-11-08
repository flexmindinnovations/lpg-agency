import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';
import { Badge } from 'primeng/badge';
import { Tab, TabList, Tabs } from 'primeng/tabs';
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
  imports: [RouterOutlet, Badge, Tabs, TabList, Tab],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="settings">
      <!-- PrimeNG route-based tabs ("Tab Menu"): no panels, the section is the
           router outlet below. The list scrolls and shows previous/next
           arrows when the tabs are wider than the screen. -->
      <p-tabs
        class="settings__tabs"
        [value]="activeRoute()"
        (valueChange)="open($event)"
        [showNavigators]="true"
      >
        <p-tablist>
          @for (group of groups(); track group.label) {
            @for (section of group.sections; track section.route) {
              <p-tab class="settings__link" [value]="section.route">
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
              </p-tab>
            }
          }
        </p-tablist>
      </p-tabs>
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

      /* The tab row is PrimeNG's own (scrolling, arrows, keyboard). Only the
         frame is ours: no panel background and a hairline under the row. */
      .settings__tabs {
        flex-shrink: 0;
        /* Same right padding as the content below, so the row ends where the
           cards do instead of running to the window edge. */
        padding-inline-end: var(--spacing-xl);
        /* Slimmer tabs than PrimeNG's default (0.875rem 1rem). */
        --p-tabs-tab-padding: 0.5rem 0.75rem;
        --p-tabs-tablist-background: transparent;
        --p-tabs-nav-button-background: transparent;
      }

      /* See-through row with the same rounded corners as the cards. */
      .settings__tabs ::ng-deep .p-tablist {
        background: transparent;
        border-radius: var(--radius-card);
        overflow: hidden;
      }

      .settings__tabs ::ng-deep .p-tablist-tab-list {
        background: transparent;
      }

      /* The scroll arrows sit over tab labels, so they keep a soft backing. */
      .settings__tabs ::ng-deep .p-tablist-nav-button {
        background: color-mix(in srgb, var(--paper-veil-color) 85%, transparent);
      }

      .settings__link {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-sm);
        white-space: nowrap;
        font-size: var(--typography-body-small-font-size);
      }

      .settings__badge {
        margin-inline-start: var(--spacing-xs);
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
  private readonly router = inject(Router);

  /** Phones waiting for approval — shown next to Linked Devices. */
  protected readonly pendingPhones = this.pendingDevices.count;
  protected readonly devicesRoute = '/settings/license/devices';

  protected readonly groups = computed(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    return visibleSettingsGroups((code) => permissions?.has(code) ?? false);
  });

  /** Re-evaluated after every navigation. */
  private readonly url = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.router.url),
    ),
    { initialValue: this.router.url },
  );

  /** The tab for the current URL, using each section's own `exact` rule. */
  protected readonly activeRoute = computed(() => {
    this.url();
    return (
      this.groups()
        .flatMap((group) => group.sections)
        .find((section) =>
          this.router.isActive(section.route, {
            paths: section.exact ? 'exact' : 'subset',
            queryParams: 'ignored',
            matrixParams: 'ignored',
            fragment: 'ignored',
          }),
        )?.route ?? ''
    );
  });

  /** A tab was chosen (click, Enter or Space): go to its section. */
  protected open(route: string | number | undefined): void {
    if (typeof route === 'string' && route !== this.activeRoute()) {
      void this.router.navigateByUrl(route);
    }
  }
}
