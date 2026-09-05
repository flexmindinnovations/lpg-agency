import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, Validators } from '@angular/forms';
import { of, startWith, switchMap } from 'rxjs';
import { FloatLabel } from 'primeng/floatlabel';

/**
 * The standard form field wrapper (doc §19) — a floating label, the
 * projected control, and hint / error text below it.
 *
 * Pass the bound `AbstractControl` via `[control]` so the field knows when
 * to surface an error (`invalid && (touched || dirty)`); `[messages]` maps
 * validator keys to copy. The error carries an icon as well as colour —
 * status is never communicated by colour alone (doc §28).
 *
 * The projected control keeps its own `id` / `formControlName`; give the
 * field the matching `for` so the floating label and the input are
 * associated for the float behaviour and for assistive tech.
 */
@Component({
  selector: 'lpg-form-field',
  standalone: true,
  imports: [FloatLabel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="lpg-field" [class.lpg-field--invalid]="showError()">
      <p-floatlabel variant="on">
        <ng-content />
        <label [attr.for]="for()">
          {{ label() }}@if (isRequired()) {<span class="lpg-field__req" aria-hidden="true">&nbsp;*</span>}
        </label>
      </p-floatlabel>

      @if (showError()) {
        <span class="lpg-field__error" role="alert">
          <i class="pi pi-exclamation-circle" aria-hidden="true"></i>
          {{ errorText() }}
        </span>
      } @else if (hint()) {
        <span class="lpg-field__hint">{{ hint() }}</span>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .lpg-field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      /* p-floatlabel renders its own wrapper; make the control fill it. */
      .lpg-field ::ng-deep .p-floatlabel {
        inline-size: 100%;
      }

      .lpg-field label {
        font-size: var(--typography-secondary-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
      }

      .lpg-field__req {
        color: var(--color-status-danger);
      }

      .lpg-field__hint {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        line-height: var(--typography-caption-line-height);
      }

      .lpg-field__error {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: var(--typography-caption-font-size);
        color: var(--color-status-danger);
        line-height: var(--typography-caption-line-height);
      }

      .lpg-field__error i {
        font-size: 12px;
      }

      /* Nudge the projected control's border to the danger colour while
         invalid — PrimeNG's own invalid styling only triggers on
         ng-invalid + ng-dirty, this covers touched-but-pristine too. */
      .lpg-field--invalid ::ng-deep .p-inputtext,
      .lpg-field--invalid ::ng-deep .p-select,
      .lpg-field--invalid ::ng-deep .p-inputnumber-input,
      .lpg-field--invalid ::ng-deep .p-autocomplete-input {
        border-color: var(--color-status-danger);
      }
    `,
  ],
})
export class FormFieldComponent {
  readonly label = input.required<string>();
  /** The `id` of the projected control — links the floating label to it. */
  readonly for = input<string>('');
  readonly hint = input<string>('');
  readonly control = input<AbstractControl | null>(null);
  /** Validator key → message. A key not present here falls back to a generic. */
  readonly messages = input<Record<string, string>>({});
  /** Force the required asterisk on/off; otherwise inferred from the control. */
  readonly required = input<boolean | null>(null);

  /**
   * `AbstractControl`'s validity / touched / dirty flags are plain
   * properties, not signals — a `computed` reading them alone would never
   * re-run. Tracking `control.events` (Angular 18+) gives the computeds a
   * real dependency that ticks on every status / touched / value change,
   * re-subscribing if the `control` input itself is swapped.
   */
  private readonly controlTick = toSignal(
    toObservable(this.control).pipe(
      switchMap((c) => (c ? c.events.pipe(startWith(null)) : of(null))),
    ),
    { initialValue: null },
  );

  protected readonly showError = computed(() => {
    this.controlTick();
    const c = this.control();
    return !!c && c.invalid && (c.touched || c.dirty);
  });

  protected readonly isRequired = computed(() => {
    this.controlTick();
    const forced = this.required();
    if (forced !== null) return forced;
    const c = this.control();
    return !!c && typeof c.hasValidator === 'function' && c.hasValidator(Validators.required);
  });

  protected readonly errorText = computed(() => {
    this.controlTick();
    const errors = this.control()?.errors;
    if (!errors) return '';
    const map = this.messages();
    const key = Object.keys(errors)[0];
    return map[key] ?? this.genericMessage(key);
  });

  private genericMessage(key: string): string {
    switch (key) {
      case 'required':
        return 'This field is required.';
      case 'email':
        return 'Enter a valid email address.';
      case 'minlength':
        return 'This value is too short.';
      case 'maxlength':
        return 'This value is too long.';
      case 'min':
        return 'This value is too low.';
      case 'max':
        return 'This value is too high.';
      case 'pattern':
        return 'This value is not in the expected format.';
      default:
        return 'This value is not valid.';
    }
  }
}
