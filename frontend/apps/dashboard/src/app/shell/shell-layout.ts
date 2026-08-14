import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui/app-shell';
import { AuthService, AuthTokenStore } from '@lpg/shared/data-access';
import { Toast } from 'primeng/toast';
import { NotificationBell } from '@lpg/notification/ui-bell';
import { NotificationDrawer } from '@lpg/notification/ui-drawer';

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
  imports: [RouterOutlet, AppShellComponent, Toast, NotificationBell, NotificationDrawer],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-app-shell
      brandName="LPG Agency"
      [navGroups]="navGroups()"
      [email]="email()"
      [role]="role()"
      (signOut)="onSignOut()"
    >
      <lpg-notification-bell shell-top-right-actions (toggle)="isDrawerVisible.set(!isDrawerVisible())" />
      <router-outlet />
    </lpg-app-shell>
    <lpg-notification-drawer [(visible)]="isDrawerVisible" />
    <p-toast position="bottom-right" />
  `,
})
export class ShellLayout {
  protected readonly isDrawerVisible = signal(false);

  private readonly authService = inject(AuthService);
  private readonly tokenStore = inject(AuthTokenStore);
  private readonly router = inject(Router);

  protected readonly email = computed(() => this.authService.principal()?.email ?? null);
  protected readonly role = computed(() => this.authService.principal()?.role ?? '');

  protected onSignOut(): void {
    this.authService.logout().subscribe(() => {
      void this.router.navigateByUrl('/login');
    });
  }

  /** Nav tree filtered to routes the current user can actually access. */
  protected readonly navGroups = computed<readonly NavGroup[]>(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    const can = (code: string) => permissions?.has(code) ?? false;

    return [
      {
        label: 'Overview',
        items: [
          { label: 'Dashboard', icon: 'pi pi-home', route: '/', exact: true },
          { label: 'Reports', icon: 'pi pi-chart-bar', route: '/reports' }
        ],
      },
      {
        label: 'Operations',
        items: [
          { label: 'Customers', icon: 'pi pi-users', route: '/customers', aliases: ['/ledger'] },
          { label: 'Orders', icon: 'pi pi-shopping-cart', route: '/orders' },
          { label: 'Dispatch', icon: 'pi pi-map', route: '/dispatch' },
          { label: 'Complaints', icon: 'pi pi-exclamation-circle', route: '/complaints' },
        ],
      },
      {
        label: 'Accounting',
        items: [
          { label: 'Invoices', icon: 'pi pi-receipt', route: '/invoices' },
        ],
      },
      {
        label: 'Logistics',
        items: [
          { label: 'Drivers', icon: 'pi pi-id-card', route: '/drivers' },
          { label: 'Vehicles', icon: 'pi pi-truck', route: '/vehicles' },
          { label: 'Inventory', icon: 'pi pi-database', route: '/inventory' },
          { label: 'Warehouses', icon: 'pi pi-warehouse', route: '/admin/warehouses' },
        ],
      },
      {
        label: 'Administration',
        items: [
          { label: 'Branches', icon: 'pi pi-building', route: '/admin/branches' },
          { label: 'Cylinder Types', icon: 'pi pi-box', route: '/admin/cylinder-types' },
          { label: 'Pricing', icon: 'pi pi-tag', route: '/admin/price-lists' },
          { label: 'Users & Roles', icon: 'pi pi-user', route: '/admin/users' },
          { label: 'Tenant Config', icon: 'pi pi-cog', route: '/admin/tenant-config' },
          { label: 'Feature Flags', icon: 'pi pi-flag', route: '/admin/feature-flags' },
          // Platform Flags is a superadmin-only tool — only shown when the
          // token carries feature_flags:manage_platform (matches the route's
          // own permissionGuard so the link is never shown to users who would
          // just be redirected away on click).
          ...(can('feature_flags:manage_platform')
            ? [{ label: 'Platform Flags', icon: 'pi pi-globe', route: '/admin/feature-flags/platform' }]
            : []),
          { label: 'Audit Log', icon: 'pi pi-history', route: '/admin/audit-log' },
        ],
      },
    ];
  });
}
