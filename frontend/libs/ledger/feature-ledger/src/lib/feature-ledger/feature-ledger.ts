import { HeaderTitlePortalDirective, PageActionsDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  input,
  signal,
  computed,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';

import { EmptyStateComponent, FormFieldComponent, HasPermissionDirective } from '@lpg/shared/ui';
import { RouterLink } from '@angular/router';

import {
  CylinderLedgerService,
  AdminCylinderTypeService,
  NotifyService,
  errorMessageFor,
  type CylinderLedgerResponse,
  type CylinderTypeResponse,
  type AppError,
} from '@lpg/shared/data-access';

interface EnrichedBalance {
  cylinder_type_id: string;
  name: string;
  quantity: number;
}

@Component({
  selector: 'lpg-feature-ledger',
  standalone: true,
  imports: [
    PageActionsDirective,
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    Select,
    InputText,
    Drawer,
    DrawerA11yDirective,
    FormFieldComponent,
    EmptyStateComponent,
    HasPermissionDirective,
    RouterLink,
  ],
  templateUrl: './feature-ledger.html',
  styleUrl: './feature-ledger.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeatureLedger implements OnInit {
  // Input from the parent (e.g. customer details panel)
  readonly customerId = input.required<string>();

  private readonly ledgerService = inject(CylinderLedgerService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly notify = inject(NotifyService);
  private readonly fb = inject(NonNullableFormBuilder);

  ledger = signal<CylinderLedgerResponse | null>(null);
  cylinderTypes = signal<CylinderTypeResponse[]>([]);
  loading = signal(false);
  /** Why the ledger could not be shown, e.g. an unknown customer (DO-22). */
  loadError = signal<string | null>(null);

  adjustModalVisible = signal(false);
  isSubmitting = signal(false);

  adjustForm = this.fb.group({
    cylinder_type_id: this.fb.control<string>('', [Validators.required]),
    delta: this.fb.control<number>(0, [Validators.required]),
    reason: this.fb.control<string>('', [Validators.required, Validators.maxLength(500)]),
  });

  protected readonly fieldMessages = {
    cylinder_type_id: { required: 'Select a cylinder type.' },
    delta: { required: 'Enter an adjustment quantity.', notZero: 'Enter a number other than 0.' },
    reason: { required: 'A reason is required.', maxlength: 'Keep it under 500 characters.' },
  };

  enrichedBalances = computed(() => {
    const l = this.ledger();
    const types = this.cylinderTypes();
    if (!l) return [];

    // Create a map for quick lookup
    const typeMap = new Map(types.map((t) => [t.id, t.name]));

    const result: EnrichedBalance[] = l.balances.map((b) => ({
      cylinder_type_id: b.cylinder_type_id,
      name: typeMap.get(b.cylinder_type_id) ?? 'Unknown Cylinder',
      quantity: b.quantity,
    }));

    // Add 0 balances for any cylinder type not present in the ledger,
    // so the UI always shows all configured cylinder types.
    const existingTypeIds = new Set(result.map((b) => b.cylinder_type_id));
    for (const t of types) {
      if (!existingTypeIds.has(t.id)) {
        result.push({
          cylinder_type_id: t.id,
          name: t.name,
          quantity: 0,
        });
      }
    }

    return result.sort((a, b) => a.name.localeCompare(b.name));
  });

  ngOnInit(): void {
    this.loadData();
  }

  loadData() {
    this.loading.set(true);
    // Load cylinder types
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
      error: () => this.notify.error('Could not load cylinder types.'),
    });

    // Load ledger
    this.loadLedger();
  }

  loadLedger() {
    this.loading.set(true);
    this.loadError.set(null);
    this.ledgerService.getLedger(this.customerId()).subscribe({
      next: (res) => {
        this.ledger.set(res);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        const status = (err as Partial<AppError> | null)?.status;
        this.loadError.set(
          status === 404
            ? 'This customer could not be found. They may have been removed, or the link is wrong.'
            : errorMessageFor(err),
        );
        this.loading.set(false);
      },
    });
  }

  openAdjustModal() {
    this.adjustForm.reset({ delta: 0 });
    this.adjustModalVisible.set(true);
  }

  closeAdjustModal() {
    this.adjustModalVisible.set(false);
  }

  onDrawerHide() {
    document.getElementById('adjust-balance-btn')?.focus();
  }

  submitAdjustment() {
    const delta = this.adjustForm.controls.delta;
    if (delta.value === 0) delta.setErrors({ notZero: true });
    if (this.adjustForm.invalid) {
      this.adjustForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    const formValue = this.adjustForm.getRawValue();

    this.ledgerService
      .adjustBalance(this.customerId(), {
        cylinder_type_id: formValue.cylinder_type_id,
        delta: formValue.delta,
        reason: formValue.reason.trim(),
      })
      .subscribe({
        next: (res) => {
          this.ledger.set(res);
          this.isSubmitting.set(false);
          this.closeAdjustModal();
          this.notify.success('Cylinder balance adjusted.');
        },
        // The app-wide error toast explains the failure.
        error: () => this.isSubmitting.set(false),
      });
  }
}
