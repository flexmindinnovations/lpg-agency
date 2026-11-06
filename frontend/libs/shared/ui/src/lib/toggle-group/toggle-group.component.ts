import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { ButtonDirective } from 'primeng/button';

/** One choice in an {@link ToggleGroupComponent}. */
export interface ToggleOption<T extends string = string> {
  readonly value: T;
  readonly label: string;
  /** Optional PrimeIcons class, e.g. `pi pi-inbox`. */
  readonly icon?: string;
}

/**
 * The one "pick one of a few" switch for page toolbars and settings: a joined
 * group of small buttons with the chosen one filled. It looks like the
 * Notifications All / Unread switch, so every page reads the same.
 *
 * Use it for two to five short choices. For a long list use a dropdown.
 */
@Component({
  selector: 'lpg-toggle-group',
  standalone: true,
  imports: [ButtonDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="toggle-group" role="group" [attr.aria-label]="ariaLabel()">
      @for (option of options(); track option.value) {
        <button
          pButton
          type="button"
          size="small"
          [severity]="option.value === value() ? 'primary' : 'secondary'"
          [disabled]="disabled()"
          [attr.aria-pressed]="option.value === value()"
          (click)="choose(option.value)"
        >
          @if (option.icon) {
            <i [class]="option.icon" aria-hidden="true"></i>
          }
          <span>{{ option.label }}</span>
        </button>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: inline-block;
      }

      .toggle-group {
        display: inline-flex;
        border-radius: var(--radius-md);
        overflow: hidden;
        border: var(--border-width, 1px) solid var(--color-border-default);
      }

      .toggle-group button {
        border-radius: 0 !important;
        border: none !important;
      }
    `,
  ],
})
export class ToggleGroupComponent<T extends string = string> {
  readonly options = input.required<readonly ToggleOption<T>[]>();
  /**
   * The chosen value. The group never changes it by itself: the page decides
   * (it may ask "are you sure?" first) and passes the new value back in.
   */
  readonly value = input.required<T>();
  /** The user picked a different option. */
  readonly valueChange = output<T>();
  /** Names the group for screen readers, e.g. "Show phones by state". */
  readonly ariaLabel = input.required<string>();
  readonly disabled = input(false);

  protected choose(next: T): void {
    if (next !== this.value()) {
      this.valueChange.emit(next);
    }
  }
}
