import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, Validators } from '@angular/forms';
import { of, startWith, switchMap } from 'rxjs';

/**
 * The standard form field wrapper (doc §19) — a 13px medium label above the
 * projected control, then hint / error text below it. One wrapper for every
 * labelled control in the app: data-entry forms and filter rows alike.
 *
 * Pass the bound `AbstractControl` via `[control]` so the field knows when to
 * surface an error (`invalid && (touched || dirty)`) and whether to show the
 * required asterisk; `[messages]` maps validator keys to copy. The error
 * carries an icon as well as colour — status is never communicated by colour
 * alone (doc §28). A filter row can omit `[control]` entirely: it then renders
 * just the label + control.
 *
 * The projected control keeps its own `id` / `formControlName`; give the field
 * the matching `for` so the label and the input are associated for assistive
 * tech. Give the control `[fluid]="true"` (or let the wrapper's fallback
 * stretch it to full width).
 *
 * `[optional]="true"` puts a muted "(Optional)" suffix next to the label
 * itself, rather than as separate hint text below the control.
 */
@Component({
  selector: 'lpg-form-field',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="lpg-field" [class.lpg-field--invalid]="showError()">
      <label class="lpg-field__label" [attr.for]="for()">
        {{ label() }}@if (isRequired()) {<span class="lpg-field__req" aria-hidden="true">*</span>} @else if (optional()) {<span class="lpg-field__optional">(Optional)</span>}
      </label>

      <ng-content />

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
        gap: 6px;
      }

      .lpg-field__label {
        font-size: var(--typography-secondary-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-primary);
        line-height: 1.3;
      }

      .lpg-field__req {
        color: var(--color-status-danger);
        margin-inline-start: 2px;
      }

      .lpg-field__optional {
        color: var(--color-text-secondary);
        font-weight: normal;
        margin-inline-start: 4px;
      }

      /* Stretch the projected control to the field width unless the call site
         already set a width (e.g. PrimeNG's [fluid]). */
      .lpg-field ::ng-deep .p-inputtext,
      .lpg-field ::ng-deep .p-select,
      .lpg-field ::ng-deep .p-multiselect,
      .lpg-field ::ng-deep .p-datepicker,
      .lpg-field ::ng-deep .p-inputnumber,
      .lpg-field ::ng-deep .p-autocomplete,
      .lpg-field ::ng-deep textarea {
        width: 100%;
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
      .lpg-field--invalid ::ng-deep .p-autocomplete-input,
      .lpg-field--invalid ::ng-deep textarea {
        border-color: var(--color-status-danger);
      }
    `,
  ],
})
export class FormFieldComponent {
  readonly label = input.required<string>();
  /** The `id` of the projected control — links the label to it. */
  readonly for = input<string>('');
  readonly hint = input<string>('');
  readonly control = input<AbstractControl | null>(null);
  /** Validator key → message. A key not present here falls back to a generic. */
  readonly messages = input<Record<string, string>>({});
  /** Force the required asterisk on/off; otherwise inferred from the control. */
  readonly required = input<boolean | null>(null);
  /** Shows a muted "(Optional)" suffix next to the label. Ignored when the
   *  field is required — a field is never both. */
  readonly optional = input(false);

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
