import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
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
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { MessageService } from 'primeng/api';
import { Select } from 'primeng/select';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';

import { FormFieldComponent } from '@lpg/shared/ui';

import {
  CylinderLedgerService,
  AdminCylinderTypeService,
  type CylinderLedgerResponse,
  type CylinderTypeResponse,
  type AppError,
} from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

interface EnrichedBalance {
  cylinder_type_id: string;
  name: string;
  quantity: number;
}

@Component({
  selector: 'lpg-feature-ledger',
  standalone: true,
  imports: [HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Select,
    InputText,
    Drawer,
    DrawerA11yDirective,
    FormFieldComponent,
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
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(NonNullableFormBuilder);

  ledger = signal<CylinderLedgerResponse | null>(null);
  cylinderTypes = signal<CylinderTypeResponse[]>([]);
  loading = signal(false);

  adjustModalVisible = signal(false);
  isSubmitting = signal(false);

  adjustForm = this.fb.group({
    cylinder_type_id: this.fb.control<string>('', [Validators.required]),
    delta: this.fb.control<number>(0, [Validators.required]),
    reason: this.fb.control<string>('', [Validators.required]),
  });

  protected readonly fieldMessages = {
    cylinder_type_id: { required: 'Select a cylinder type.' },
    delta: { required: 'Enter an adjustment quantity.' },
    reason: { required: 'A reason is required.' },
  };

  enrichedBalances = computed(() => {
    const l = this.ledger();
    const types = this.cylinderTypes();
    if (!l) return [];
    
    // Create a map for quick lookup
    const typeMap = new Map(types.map(t => [t.id, t.name]));

    const result: EnrichedBalance[] = l.balances.map(b => ({
      cylinder_type_id: b.cylinder_type_id,
      name: typeMap.get(b.cylinder_type_id) ?? 'Unknown Cylinder',
      quantity: b.quantity
    }));

    // Add 0 balances for any cylinder type not present in the ledger, 
    // so the UI always shows all configured cylinder types.
    const existingTypeIds = new Set(result.map(b => b.cylinder_type_id));
    for (const t of types) {
      if (!existingTypeIds.has(t.id)) {
        result.push({
          cylinder_type_id: t.id,
          name: t.name,
          quantity: 0
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
      error: () => this.showError('Failed to load cylinder types')
    });

    // Load ledger
    this.loadLedger();
  }

  loadLedger() {
    this.loading.set(true);
    this.ledgerService.getLedger(this.customerId()).subscribe({
      next: (res) => {
        this.ledger.set(res);
        this.loading.set(false);
      },
      error: () => {
        this.showError('Failed to load cylinder ledger');
        this.loading.set(false);
      }
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
    if (this.adjustForm.invalid) {
      this.adjustForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    const formValue = this.adjustForm.getRawValue();

    this.ledgerService.adjustBalance(this.customerId(), {
      cylinder_type_id: formValue.cylinder_type_id,
      delta: formValue.delta,
      reason: formValue.reason,
    }).subscribe({
      next: (res) => {
        this.ledger.set(res);
        this.isSubmitting.set(false);
        this.closeAdjustModal();
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Ledger balance adjusted.',
        });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        if (isAppError(err.error)) {
          this.showError(err.error.detail || 'Failed to adjust balance');
        } else {
          this.showError('Failed to adjust balance');
        }
      },
    });
  }

  private showError(msg: string) {
    this.messageService.add({
      severity: 'error',
      summary: 'Error',
      detail: msg,
    });
  }
}
