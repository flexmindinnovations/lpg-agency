import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Application root — a bare router outlet.
 *
 * The shell chrome (`AppShellComponent`, nav groups) moved to
 * `shell/shell-layout.ts` in Phase 6 (ADR-036): `/login` needs to render
 * without a sidebar/top-bar around it, so the root itself can no longer
 * assume every route wants the shell. `app.routes.ts` decides that per
 * route instead.
 */
@Component({
  selector: 'lpg-root',
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {}
