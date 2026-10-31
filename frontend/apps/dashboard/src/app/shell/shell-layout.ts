import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet } from '@angular/router';
import { interval, startWith } from 'rxjs';
import { AppShellComponent, type NavGroup, type NavItem } from '@lpg/shared/ui/app-shell';
import {
  AuthService,
  AuthTokenStore,
  HARD_NAVIGATE,
  LicenseStatusStore,
} from '@lpg/shared/data-access';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { NotificationBell } from '@lpg/notification/ui-bell';
import { NotificationDrawer } from '@lpg/notification/ui-drawer';
import { CommandPaletteComponent } from '../command-palette/command-palette.component';
import { CommandPaletteService } from '../command-palette/command-palette.service';
import { visibleSettingsGroups } from '../settings/settings-sections';

/** How often to nag a tenant in its license grace period — matches
 * `NotificationBell`'s own 5-minute polling interval convention. */
const GRACE_REMINDER_INTERVAL_MS = 300_000;

/**
 * Hosts the shared `AppShellComponent` for every authenticated route.
 *
 * Moved out of the app root (`app.ts`) in Phase 6 (ADR-036) so `/login` can
 * render without the sidebar/top-bar chrome around it: `app.routes.ts`
 * mounts this as the parent of every route that needs the shell, guarded by
 * `authGuard`, while `/login` stays a sibling route outside it. `app.html`
 * is now just a bare `<router-outlet />`.
 *
 * Imports from `@lpg/shared/ui/app-shell` (a secondary entry point), not the
 * library's main `@lpg/shared/ui` barrel — this component is eagerly loaded
 * (it's the parent shell `component:`, not a lazy route), so anything it
 * imported from the main barrel would end up in the initial bundle,
 * including `ag-grid-community` transitively via `DataGridComponent`'s
 * co-located export. Found via a real bundle-budget failure the moment
 * Phase 7's admin pages became the first real `DataGridComponent` consumer.
 */
@Component({
  selector: 'lpg-shell-layout',
  standalone: true,
  imports: [
    RouterOutlet,
    AppShellComponent,
    ToastModule,
    ConfirmDialogModule,
    NotificationBell,
    NotificationDrawer,
    CommandPaletteComponent,
  ],
  // No component-level MessageService provider — it's already provided at
  // root (app.config.ts). A local override here used to shadow that root
  // instance for this shell's whole subtree, meaning NotifyService (root-
  // scoped, providedIn: 'root') and this <p-toast> ended up bound to two
  // different MessageService instances: NotifyService always resolves its
  // own dependencies against the root injector (where it's registered),
  // regardless of which component ends up calling it — messages it
  // published were never seen by this shell's toast. One shared instance
  // is also just correct for a genuinely *global* handler.
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-app-shell
      brandName="LPG Agency"
      [navGroups]="navGroups()"
      [email]="email()"
      [role]="role()"
      (signOut)="onSignOut()"
    >
      <div shell-top-right-actions class="shell-actions">
        <button
          type="button"
          class="cmdk-trigger"
          (click)="commandPalette.open()"
          aria-label="Open command palette"
        >
          <i class="pi pi-search" aria-hidden="true"></i>
          <span>Search</span>
          <kbd>Ctrl K</kbd>
        </button>
        <lib-notification-bell (toggled)="isDrawerVisible.set(!isDrawerVisible())" />
      </div>
      <router-outlet />
    </lpg-app-shell>
    <lib-notification-drawer [(visible)]="isDrawerVisible" />
    <lpg-command-palette [navItems]="flatNavItems()" />
    <p-toast position="bottom-right" [preventDuplicates]="true" />
    <p-confirmdialog />
  `,
  styles: [
    `
      .shell-actions {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .cmdk-trigger {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: 6px var(--spacing-sm);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-input);
        /* Page-ground fill: secondary text on the overlay tint was 4.39:1. */
        background: var(--color-surface-base);
        color: var(--color-text-secondary);
        font: inherit;
        font-size: var(--typography-secondary-font-size);
        cursor: pointer;
        transition: border-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .cmdk-trigger:hover {
        border-color: var(--color-border-strong);
      }

      .cmdk-trigger .pi-search {
        font-size: var(--icon-size-sm);
      }

      .cmdk-trigger kbd {
        padding: 1px 5px;
        border: var(--border-width) solid var(--color-border-strong);
        border-radius: var(--radius-xs);
        background: var(--color-surface-base);
        font-size: 10px;
      }

      @media (max-width: 768px) {
        .cmdk-trigger span,
        .cmdk-trigger kbd {
          display: none;
        }
      }
    `,
  ],
})
export class ShellLayout {
  protected readonly isDrawerVisible = signal(false);

  private readonly authService = inject(AuthService);
  private readonly tokenStore = inject(AuthTokenStore);
  private readonly hardNavigate = inject(HARD_NAVIGATE);
  private readonly licenseStatusStore = inject(LicenseStatusStore);
  private readonly messageService = inject(MessageService);
  protected readonly commandPalette = inject(CommandPaletteService);

  protected readonly email = computed(() => this.authService.principal()?.email ?? null);
  protected readonly role = computed(() => this.authService.principal()?.role ?? '');

  constructor() {
    // Nags every 5 minutes while the license is in its 1-day grace window
    // — full access continues, this is a reminder to renew, not a block.
    // Keeps nav usable throughout, unlike the hard `licenseGuard` gate.
    interval(GRACE_REMINDER_INTERVAL_MS)
      .pipe(startWith(0), takeUntilDestroyed())
      .subscribe(() => {
        if (this.licenseStatusStore.status()?.status === 'grace') {
          this.messageService.add({
            severity: 'warn',
            summary: 'License expiring soon',
            detail:
              'This tenant’s license is in its grace period. Renew it to avoid losing access.',
            life: 8000,
          });
        }
      });
  }

  protected onSignOut(): void {
    // A full page load, so signing out lands on the login page even from a tab left open
    // across a deploy, where the router can no longer fetch the lazy-loaded login chunk.
    this.authService.logout().subscribe(() => this.hardNavigate('/login'));
  }

  /** Nav tree filtered to routes the current user can actually access. */
  protected readonly navGroups = computed<readonly NavGroup[]>(() => {
    const principal = this.tokenStore.principal();
    const can = (code: string) => principal?.permissions.has(code) ?? false;
    // `driver` holds these permission codes only for narrow, single-record
    // API calls tied to their own delivery workflow, not to browse the
    // full staff-facing list/planning page — same reasoning and role list
    // as `permission.guard.ts`'s route guards for these paths.
    const canBrowse = (code: string) => can(code) && principal?.role !== 'driver';

    type ConditionalNavItem = NavItem & { condition?: boolean };
    const withoutCondition = (item: ConditionalNavItem): NavItem => {
      const copy = { ...item };
      delete copy.condition;
      return copy;
    };
    const buildGroup = (label: string, items: ConditionalNavItem[]) => {
      const filtered = items.filter((i) => i.condition !== false);
      return filtered.length > 0 ? [{ label, items: filtered.map(withoutCondition) }] : [];
    };

    return [
      ...buildGroup('Overview', [
        { label: 'Dashboard', icon: 'pi pi-home', route: '/', exact: true },
        {
          label: 'Reports',
          icon: 'pi pi-chart-bar',
          route: '/reports',
          condition: can('reports:read'),
        },
        // No permission guard on this route (any authenticated user's own
        // notifications) — always shown, matching Dashboard above.
        { label: 'Notifications', icon: 'pi pi-bell', route: '/notifications' },
        {
          label: 'AI Command Center',
          icon: 'pi pi-comments',
          route: '/ai-assistant',
          condition: can('ai:read'),
        },
      ]),
      ...buildGroup('Operations', [
        {
          label: 'Customers',
          icon: 'pi pi-users',
          route: '/customers',
          aliases: ['/ledger'],
          condition: canBrowse('customers:read'),
        },
        {
          label: 'Orders',
          icon: 'pi pi-shopping-cart',
          route: '/orders',
          condition: can('orders:read'),
        },
        {
          label: 'Dispatch',
          icon: 'pi pi-map',
          route: '/dispatch',
          condition: canBrowse('routes:read'),
        },
        {
          label: 'Complaints',
          icon: 'pi pi-exclamation-circle',
          route: '/complaints',
          condition: can('complaints.manage'),
        },
      ]),
      ...buildGroup('Accounting', [
        {
          label: 'Invoices',
          icon: 'pi pi-receipt',
          route: '/invoices',
          condition: can('invoices:read'),
        },
        {
          label: 'Cash Handovers',
          icon: 'pi pi-money-bill',
          route: '/cash-handovers',
          condition: can('cash_handovers:review'),
        },
      ]),
      ...buildGroup('Logistics', [
        {
          label: 'Drivers',
          icon: 'pi pi-id-card',
          route: '/drivers',
          condition: canBrowse('drivers:read'),
        },
        {
          label: 'Vehicles',
          icon: 'pi pi-truck',
          route: '/vehicles',
          condition: canBrowse('vehicles:read'),
        },
        {
          label: 'Inventory',
          icon: 'pi pi-database',
          route: '/inventory',
          condition: can('inventory:read'),
        },
        {
          label: 'Godowns',
          icon: 'pi pi-warehouse',
          route: '/admin/warehouses',
          condition: can('tenant:configure'),
        },
        {
          label: 'Scales',
          icon: 'pi pi-sliders-h',
          route: '/scales',
          condition: can('weighment:record'),
        },
        {
          label: 'Cylinder Units',
          icon: 'pi pi-qrcode',
          route: '/cylinder-units',
          condition: can('cylinder_units:read'),
        },
        {
          label: 'Compliance Calendar',
          icon: 'pi pi-shield',
          route: '/compliance-calendar',
          condition: can('compliance:read'),
        },
      ]),
      ...buildGroup('Administration', [
        {
          label: 'Branches',
          icon: 'pi pi-building',
          route: '/admin/branches',
          condition: can('tenant:configure'),
        },
        {
          label: 'Cylinder Types',
          icon: 'pi pi-box',
          route: '/admin/cylinder-types',
          condition: can('tenant:configure'),
        },
        {
          label: 'Pricing',
          icon: 'pi pi-tag',
          route: '/admin/price-lists',
          condition: can('tenant:configure'),
        },
        {
          label: 'Users & Roles',
          icon: 'pi pi-user',
          route: '/admin/users',
          condition: can('users:manage'),
        },
        {
          label: 'Employees',
          icon: 'pi pi-briefcase',
          route: '/admin/employees',
          condition: can('users:manage'),
        },
        {
          label: 'Audit Log',
          icon: 'pi pi-history',
          route: '/admin/audit-log',
          condition: can('audit:read'),
        },
      ]),
      // Always shown: Settings opens on the personal Account section, which
      // every role has; agency-wide sections appear inside it by permission.
      {
        items: [{ label: 'Settings', icon: 'pi pi-cog', route: '/settings' }],
      },
    ];
  });

  /** Flat, permission-filtered nav destinations — feeds the command palette.
   * Settings sections are listed individually so "License" or "Feature Flags"
   * stay one search away even though they no longer have a sidebar entry. */
  protected readonly flatNavItems = computed(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    const sections = visibleSettingsGroups((code) => permissions?.has(code) ?? false).flatMap(
      (group) => group.sections,
    );
    return [...this.navGroups().flatMap((g) => g.items), ...sections];
  });
}
