import {
  ChangeDetectionStrategy,
  Component,
  Input,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { AutoComplete } from 'primeng/autocomplete';
import type { AutoCompleteCompleteEvent } from 'primeng/types/autocomplete';
import { CustomerService, type CustomerResponse } from '@lpg/shared/data-access';

/**
 * Customer search-as-you-type field for the Create Order drawer.
 *
 * Single consumer today — kept local to `feature-orders` rather than
 * promoted to `@lpg/shared/ui`, matching this codebase's own rule of
 * promoting a component only once a second caller actually needs it.
 */
@Component({
  selector: 'lpg-customer-autocomplete',
  standalone: true,
  imports: [FormsModule, AutoComplete],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-autocomplete
      [(ngModel)]="selected"
      (ngModelChange)="onModelChange($event)"
      [suggestions]="suggestions()"
      (completeMethod)="search($event)"
      optionLabel="full_name"
      [delay]="300"
      [minQueryLength]="2"
      [autoOptionFocus]="true"
      [placeholder]="placeholder"
      [inputId]="inputId"
      [disabled]="disabled()"
      styleClass="w-full"
      [fluid]="true"
      (onBlur)="onBlur()"
    >
      <ng-template let-customer #item>
        <div>
          <strong>{{ customer.full_name }}</strong>
          <span class="customer-autocomplete__meta">
            · {{ customer.phone_number }}
            @if (customer.consumer_number) {
              · {{ customer.consumer_number }}
            }
            @if (customer.status !== 'active') {
              · {{ customer.status }}
            }
          </span>
        </div>
      </ng-template>
    </p-autocomplete>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .customer-autocomplete__meta {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
    `,
  ],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomerAutocomplete),
      multi: true,
    },
  ],
})
export class CustomerAutocomplete implements ControlValueAccessor {
  private readonly customerService = inject(CustomerService);

  @Input() placeholder = 'Name, phone or consumer no.';
  @Input() inputId = 'customer_autocomplete';

  protected readonly suggestions = signal<CustomerResponse[]>([]);
  protected readonly disabled = signal(false);
  protected selected: CustomerResponse | string | null = null;

  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnChange
  private onChange: (value: CustomerResponse | null) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnTouched
  private onTouched: () => void = () => {};

  private latestQuery = '';

  protected search(event: AutoCompleteCompleteEvent): void {
    const query = event.query?.replace(/\s+/g, ' ').trim() ?? '';
    this.latestQuery = query;
    if (query.length < 2) {
      this.suggestions.set([]);
      return;
    }
    this.customerService.list(0, 20, query).subscribe({
      next: (page) => {
        // An answer for an older query is dropped.
        if (query === this.latestQuery) this.suggestions.set(page.items);
      },
      error: () => this.suggestions.set([]),
    });
  }

  /**
   * While typing, PrimeNG puts the typed text in the model; the form only
   * ever sees a picked customer or `null`, so the booking form never acts
   * on half-typed text (DO-09).
   */
  protected onModelChange(value: CustomerResponse | string | null): void {
    const customer = typeof value === 'object' ? value : null;
    if (customer === this.emitted) return;
    this.emitted = customer;
    this.onChange(customer);
  }

  private emitted: CustomerResponse | null = null;

  protected onBlur(): void {
    this.onTouched();
  }

  writeValue(value: CustomerResponse | null): void {
    this.selected = value;
    this.emitted = value;
  }

  registerOnChange(fn: (value: CustomerResponse | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }
}
