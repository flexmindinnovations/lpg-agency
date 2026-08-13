import { ChangeDetectionStrategy, Component, forwardRef, inject, signal } from '@angular/core';
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
      [placeholder]="placeholder"
      [inputId]="inputId"
      [disabled]="disabled()"
      styleClass="w-full"
      [fluid]="true"
    >
      <ng-template let-customer #item>
        <div>
          <strong>{{ customer.full_name }}</strong>
          <span class="customer-autocomplete__meta"> · {{ customer.phone_number }}</span>
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

  placeholder = 'Search by name or phone…';
  inputId = 'customer_autocomplete';

  protected readonly suggestions = signal<CustomerResponse[]>([]);
  protected readonly disabled = signal(false);
  protected selected: CustomerResponse | null = null;

  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnChange
  private onChange: (value: CustomerResponse | null) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnTouched
  private onTouched: () => void = () => {};

  protected search(event: AutoCompleteCompleteEvent): void {
    const query = event.query?.trim();
    if (!query) {
      this.suggestions.set([]);
      return;
    }
    this.customerService.list(0, 20, query).subscribe({
      next: (page) => this.suggestions.set(page.items),
      error: () => this.suggestions.set([]),
    });
  }

  protected onModelChange(value: CustomerResponse | null): void {
    this.onChange(value);
    this.onTouched();
  }

  writeValue(value: CustomerResponse | null): void {
    this.selected = value;
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
