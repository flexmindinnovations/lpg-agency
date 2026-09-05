import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from '@lpg/shared/design-tokens';

/**
 * Application root — a bare router outlet.
 *
 * The shell chrome (`AppShellComponent`, nav groups) moved to
 * `shell/shell-layout.ts` in Phase 6 (ADR-036): `/login` needs to render
 * without a sidebar/top-bar around it, so the root itself can no longer
 * assume every route wants the shell. `app.routes.ts` decides that per
 * route instead.
 *
 * `ThemeService` is injected here purely to instantiate it at bootstrap so
 * the theme (dark by default since Phase 29) is applied to `<html>` before
 * the first route renders — including `/login` and the other pre-shell
 * screens, which don't otherwise touch it.
 */
@Component({
  selector: 'lpg-root',
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  constructor() {
    // Touch ThemeService so its constructor effect runs at bootstrap and
    // stamps `data-theme` on `<html>` before the first route paints.
    inject(ThemeService);
  }
}
