import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui';

/**
 * Hosts the shared `AppShellComponent` for every authenticated route.
 *
 * Moved out of the app root (`app.ts`) in Phase 6 (ADR-036) so `/login` can
 * render without the sidebar/top-bar chrome around it: `app.routes.ts`
 * mounts this as the parent of every route that needs the shell, guarded by
 * `authGuard`, while `/login` stays a sibling route outside it. `app.html`
 * is now just a bare `<router-outlet />`.
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
  ];
}
