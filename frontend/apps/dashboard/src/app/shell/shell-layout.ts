import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui/app-shell';

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
  imports: [RouterOutlet, AppShellComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-app-shell brandName="LPG Agency" [navGroups]="navGroups">
      <router-outlet />
    </lpg-app-shell>
  `,
})
export class ShellLayout {
  protected readonly navGroups: readonly NavGroup[] = [
    {
      items: [{ label: 'Home', icon: 'pi pi-home', route: '/', exact: true }],
    },
    {
      label: 'Administration',
      items: [
        { label: 'Branches', icon: 'pi pi-building', route: '/admin/branches' },
        { label: 'Warehouses', icon: 'pi pi-warehouse', route: '/admin/warehouses' },
        { label: 'Cylinder Types', icon: 'pi pi-box', route: '/admin/cylinder-types' },
        { label: 'Tenant Config', icon: 'pi pi-cog', route: '/admin/tenant-config' },
        { label: 'Pricing', icon: 'pi pi-tag', route: '/admin/price-lists' },
        { label: 'Feature Flags', icon: 'pi pi-flag', route: '/admin/feature-flags' },
        { label: 'Users', icon: 'pi pi-users', route: '/admin/users' },
        { label: 'Audit Log', icon: 'pi pi-history', route: '/admin/audit-log' },
      ],
    },
  ];
}
