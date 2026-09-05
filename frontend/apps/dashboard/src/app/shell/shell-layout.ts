import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterOutlet } from '@angular/router';
import { interval, startWith } from 'rxjs';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui/app-shell';
import { AuthService, AuthTokenStore, LicenseStatusStore } from '@lpg/shared/data-access';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { NotificationBell } from '@lpg/notification/ui-bell';
import { NotificationDrawer } from '@lpg/notification/ui-drawer';
import { CommandPaletteComponent } from '../command-palette/command-palette.component';
import { CommandPaletteService } from '../command-palette/command-palette.service';

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
  providers: [MessageService],
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
    <p-toast position="bottom-right" />
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
        background: var(--color-surface-overlay);
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
  private readonly router = inject(Router);
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
    this.authService.logout().subscribe(() => {
      void this.router.navigateByUrl('/login');
    });
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

    const buildGroup = (label: string, items: (any & { condition?: boolean })[]) => {
      const filtered = items.filter((i) => i.condition !== false);
      return filtered.length > 0
        ? [{ label, items: filtered.map(({ condition, ...rest }) => rest) }]
        : [];
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
        { label: 'Dispatch', icon: 'pi pi-map', route: '/dispatch', condition: canBrowse('routes:read') },
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
          label: 'Warehouses',
          icon: 'pi pi-warehouse',
          route: '/admin/warehouses',
          condition: can('tenant:configure'),
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
          label: 'Tenant Config',
          icon: 'pi pi-cog',
          route: '/admin/tenant-config',
          condition: can('tenant:configure'),
        },
        {
          label: 'Feature Flags',
          icon: 'pi pi-flag',
          route: '/admin/feature-flags',
          exact: true,
          condition: can('feature_flags:manage_tenant'),
        },
        {
          label: 'License',
          icon: 'pi pi-key',
          route: '/admin/license',
          exact: true,
          condition: can('license:manage_tenant'),
        },
        {
          label: 'Linked Devices',
          icon: 'pi pi-mobile',
          route: '/admin/license/devices',
          condition: can('license:manage_tenant'),
        },
        {
          label: 'Audit Log',
          icon: 'pi pi-history',
          route: '/admin/audit-log',
          condition: can('audit:read'),
        },
      ]),
    ];
  });

  /** Flat, permission-filtered nav destinations — feeds the command palette. */
  protected readonly flatNavItems = computed(() => this.navGroups().flatMap((g) => g.items));
}
