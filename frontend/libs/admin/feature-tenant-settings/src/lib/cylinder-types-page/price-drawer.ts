import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import {
  AdminPriceListService,
  NotifyService,
  type BranchResponse,
  type CylinderTypeResponse,
  type PriceListEntryResponse,
} from '@lpg/shared/data-access';
import {
  DrawerA11yDirective,
  FormFieldComponent,
  formatCurrencyInr,
  validateForSubmit,
} from '@lpg/shared/ui';
import { currentPrices, customerTypeOptions, defaultCustomerType, priceHint } from './price-book';

/**
 * Sets or changes one cylinder's price. A new row is added each time, so the
 * old price stays on past invoices and in the history.
 */
@Component({
  selector: 'lpg-price-drawer',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    FormFieldComponent,
    InputText,
    Select,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-drawer
      [visible]="!!cylinderType()"
      (onHide)="closed.emit()"
      position="right"
      [modal]="true"
      [closeOnEscape]="true"
      [header]="title()"
      styleClass="w-full"
      [style]="{ width: '100%', maxWidth: 'var(--drawer-width)' }"
    >
      @if (cylinderType(); as type) {
        <form [formGroup]="form" (ngSubmit)="save()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
            <p class="page-lede">
              <strong>{{ type.name }}</strong>
            </p>
            <lpg-form-field
              label="Customer type"
              for="price-customer-type"
              [control]="form.controls.customerType"
            >
              <p-select
                [filter]="true"
                [resetFilterOnHide]="true"
                inputId="price-customer-type"
                formControlName="customerType"
                [options]="customerTypes"
                optionLabel="label"
                optionValue="value"
                appendTo="body"
                [fluid]="true"
              />
            </lpg-form-field>
            @if (branches().length > 1) {
              <lpg-form-field label="Branch" for="price-branch" [control]="form.controls.branchId">
                <p-select
                  [filter]="true"
                  [resetFilterOnHide]="true"
                  inputId="price-branch"
                  formControlName="branchId"
                  [options]="branches()"
                  optionLabel="name"
                  optionValue="id"
                  placeholder="All branches"
                  [showClear]="true"
                  appendTo="body"
                  [fluid]="true"
                />
              </lpg-form-field>
            }
            <p class="current-price" role="status">{{ currentText() }}</p>
            <lpg-form-field
              label="New price (₹)"
              for="price-value"
              [control]="form.controls.price"
              [hint]="hint()"
              [messages]="{ required: 'Enter the price.', min: 'The price must be above 0.' }"
            >
              <input
                pInputText
                id="price-value"
                type="number"
                step="0.01"
                inputmode="decimal"
                formControlName="price"
                [fluid]="true"
              />
            </lpg-form-field>
            <p class="current-price">
              Used from now on, including orders not yet confirmed. Invoices already issued do not
              change.
            </p>
          </div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="closed.emit()">
              Cancel
            </button>
            <button pButton type="submit" [disabled]="saving()">
              @if (saving()) {
                <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
              }
              Save price
            </button>
          </div>
        </form>
      }
    </p-drawer>
  `,
  styles: [
    `
      .current-price {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
    `,
  ],
})
export class PriceDrawer {
  /** The cylinder being priced; `null` closes the drawer. */
  readonly cylinderType = input<CylinderTypeResponse | null>(null);
  /** Filled in to start with, e.g. a price that failed to save a moment ago. */
  readonly suggestedPrice = input<number | null>(null);
  readonly prices = input<readonly PriceListEntryResponse[]>([]);
  /** Branches that can have their own price; with one, the field is not shown. */
  readonly branches = input<BranchResponse[]>([]);
  readonly includesGst = input(false);

  readonly closed = output<void>();
  readonly saved = output<void>();

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly priceListService = inject(AdminPriceListService);
  private readonly notify = inject(NotifyService);

  protected readonly customerTypes = customerTypeOptions;
  protected readonly saving = signal(false);
  protected readonly form = this.formBuilder.group({
    customerType: ['domestic' as string, [Validators.required]],
    branchId: [null as string | null],
    price: [null as number | null, [Validators.required, Validators.min(0.01)]],
  });
  private readonly values = toSignal(this.form.valueChanges, { initialValue: this.form.value });

  /** The price now in force for exactly what is chosen, if any. */
  private readonly current = computed(() => {
    const type = this.cylinderType();
    if (!type) return { own: null, allBranches: null };
    const { customerType, branchId } = this.values();
    const inForce = currentPrices(this.prices(), type.id).filter(
      (p) => p.customer_type === customerType,
    );
    return {
      own: inForce.find((p) => p.branch_id === (branchId || null)) ?? null,
      allBranches: inForce.find((p) => p.branch_id === null) ?? null,
    };
  });

  protected readonly title = computed(() => {
    const type = this.cylinderType();
    return type && currentPrices(this.prices(), type.id).length > 0 ? 'Change price' : 'Set price';
  });

  protected readonly currentText = computed(() => {
    const { own, allBranches } = this.current();
    if (own) return `Price now: ${formatCurrencyInr(own.price)}`;
    if (this.values().branchId && allBranches) {
      return `This branch now uses the all-branches price: ${formatCurrencyInr(allBranches.price)}`;
    }
    return 'No price yet for this choice.';
  });

  protected readonly hint = computed(() =>
    priceHint(this.includesGst(), this.cylinderType()?.gst_rate_percent, this.values().price),
  );

  constructor() {
    const typeId = computed(() => this.cylinderType()?.id ?? null);
    effect(() => {
      typeId();
      untracked(() =>
        this.form.reset({
          customerType: defaultCustomerType(this.cylinderType()?.category),
          branchId: null,
          price: this.suggestedPrice(),
        }),
      );
    });
  }

  protected save(): void {
    const type = this.cylinderType();
    if (!type || this.saving() || !validateForSubmit(this.form)) return;
    const { customerType, branchId, price } = this.form.getRawValue();
    this.saving.set(true);
    this.priceListService
      .setPrice(type.id, customerType, Number(price), branchId || null)
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.notify.success(`Price of "${type.name}" saved.`);
          this.saved.emit();
        },
        // The server's message is shown by the global error toast.
        error: () => this.saving.set(false),
      });
  }
}
