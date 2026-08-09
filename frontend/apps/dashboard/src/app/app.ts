import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppShellComponent, type NavGroup } from '@lpg/shared/ui';

/**
 * Application root: wires the shared `AppShellComponent` to this app's
 * navigation model.
 *
 * `navGroups` intentionally lists only "Home" — there are no business
 * modules yet (Customer, Inventory, Order, Delivery, Accounting each arrive
 * in their own phase, behind their own plan). The shell itself is fully
 * data-driven, so extending this list is the only change a future phase
 * needs to make here.
 */
@Component({
  selector: 'lpg-root',
  standalone: true,
  imports: [RouterOutlet, AppShellComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  protected readonly navGroups: readonly NavGroup[] = [
    {
      items: [{ label: 'Home', icon: 'pi pi-home', route: '/', exact: true }],
    },
  ];
}
