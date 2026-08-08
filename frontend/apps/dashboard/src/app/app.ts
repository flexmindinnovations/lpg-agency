import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ThemeService, type ThemePreference } from '@lpg/shared/design-tokens';

/**
 * Application shell: top bar, sidebar navigation, routed content.
 *
 * Foundation only. There are no business pages — Customer, Inventory, Order,
 * Delivery and Accounting screens each arrive in their own phase, behind their
 * own plan.
 */
@Component({
  selector: 'lpg-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  private readonly themeService = inject(ThemeService);

  protected readonly themePreference = this.themeService.preference;
  protected readonly activeTheme = this.themeService.activeTheme;

  protected readonly themeOptions = computed<readonly ThemePreference[]>(() => [
    'system',
    ...this.themeService.availableThemes,
  ]);

  protected setTheme(value: string): void {
    this.themeService.setPreference(value as ThemePreference);
  }

  protected themeLabel(preference: ThemePreference): string {
    return preference === 'high-contrast'
      ? 'High contrast'
      : preference.charAt(0).toUpperCase() + preference.slice(1);
  }
}
