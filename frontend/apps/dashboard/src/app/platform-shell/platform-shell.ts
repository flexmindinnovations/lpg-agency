import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui/app-shell';
import { AuthService, AuthTokenStore } from '@lpg/shared/data-access';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';

/**
 * Hosts `AppShellComponent` for every `/platform` route — the
 * `super_admin` control-plane sibling of `ShellLayout`, mounted as its own
 * top-level route rather than a branch inside `ShellLayout` (same
 * shell-sibling precedent `/login`/`/license-required` already establish,
 * ADR-036) since a `PlatformPrincipal` session has no tenant to render the
 * tenant dashboard's nav around.
 *
 * No `licenseGuard` (a super_admin isn't gated by any tenant's license) and
 * no notification bell/drawer (`@lpg/notification/*` calls tenant-scoped
 * endpoints a null-tenant session can't reach) — otherwise mirrors
 * `ShellLayout`'s shape.
 */
@Component({
  selector: 'lpg-platform-shell',
  standalone: true,
  imports: [RouterOutlet, AppShellComponent, ToastModule, ConfirmDialogModule],
  providers: [MessageService],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-app-shell
      brandName="Platform Console"
      brandIcon="pi pi-shield"
      [navGroups]="navGroups()"
      [email]="email()"
      [role]="role()"
      (signOut)="onSignOut()"
    >
      <router-outlet />
    </lpg-app-shell>
    <p-toast position="bottom-right" />
    <p-confirmdialog />
  `,
})
export class PlatformShell {
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

  /** Nav tree filtered to the platform permissions the current session
   * actually carries — same `can()`/`buildGroup` shape `ShellLayout` uses. */
  protected readonly navGroups = computed<readonly NavGroup[]>(() => {
    const permissions = this.tokenStore.principal()?.permissions;
    const can = (code: string) => permissions?.has(code) ?? false;

    const items = [
      { label: 'Agencies', icon: 'pi pi-building', route: '/platform/agencies', condition: can('tenant:manage_platform') },
      { label: 'Licenses', icon: 'pi pi-key', route: '/platform/licenses', condition: can('license:manage_platform') },
      { label: 'Feature Flags', icon: 'pi pi-flag', route: '/platform/feature-flags', condition: can('feature_flags:manage_platform') },
    ].filter((item) => item.condition);

    return items.length > 0
      ? [{ label: 'Platform Console', items: items.map(({ condition: _condition, ...rest }) => rest) }]
      : [];
  });
}
