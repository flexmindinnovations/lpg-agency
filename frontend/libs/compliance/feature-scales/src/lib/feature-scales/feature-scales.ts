import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { map, type Observable } from 'rxjs';
import {
  DataGridComponent,
  type DataGridColumn,
  DocumentUploadComponent,
  FormFieldComponent,
  HasPermissionDirective,
  StatusChipCell,
  type ChipSeverity,
  toSentenceCase,
} from '@lpg/shared/ui';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputText } from 'primeng/inputtext';
import { InputNumber } from 'primeng/inputnumber';
import { Message } from 'primeng/message';
import { MessageService } from 'primeng/api';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { Tag } from 'primeng/tag';
import {
  AdminWarehouseService,
  DocumentService,
  WeighmentService,
  type AppError,
  type ScaleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

/** `dd-mm-yyyy`-picker value → `yyyy-mm-dd` API string, or `undefined`. */
function formatDateForApi(value: unknown): string | undefined {
  if (!value) return undefined;
  const d = new Date(value as string | number | Date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_SCALE_ASSET_TAG':
      return 'A scale with this asset tag is already registered at this warehouse.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

/** MDG 2022 cl. 1.2(ii)(iii) — mirrors the backend's hard-enforced
 * `Scale.MAX_LEAST_COUNT_GRAMS` (`domain/compliance/scale.py`) so the form
 * rejects an over-spec scale before the round-trip, not just after. */
const MAX_LEAST_COUNT_GRAMS = 10;

@Component({
  selector: 'lpg-feature-scales',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    FormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    InputNumber,
    Drawer,
    DrawerA11yDirective,
    Message,
    Select,
    Tag,
    DatePicker,
    DataGridComponent,
    FormFieldComponent,
    DocumentUploadComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-scales.html',
  styleUrl: './feature-scales.css',
})
export class FeatureScales implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly weighmentService = inject(WeighmentService);
  private readonly documentService = inject(DocumentService);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly messageService = inject(MessageService);

  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    active: 'success',
    inactive: 'secondary',
  };

  protected readonly statusOptions = [
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
  ];

  protected readonly expiryFilterOptions = [
    { label: 'All scales', value: 'all' },
    { label: 'Certificate expiring ≤30d', value: 'expiring' },
    { label: 'Certificate expired', value: 'expired' },
  ];

  protected readonly toSentenceCase = toSentenceCase;
  protected readonly maxLeastCountGrams = MAX_LEAST_COUNT_GRAMS;

  protected statusSeverity(status: string): ChipSeverity {
    return FeatureScales.STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected readonly scales = signal<ScaleResponse[]>([]);
  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly expiryFilter = signal<'all' | 'expiring' | 'expired'>('all');

  protected readonly warehouseNameById = computed(() => {
    const map = new Map<string, string>();
    for (const w of this.warehouses()) map.set(w.id, w.name);
    return map;
  });

  // Modal visibility
  protected readonly showRegisterModal = signal(false);

  // Detail drawer — view mode shows the scale's current data; edit mode
  // swaps in the recalibration form (new certificate + expiry only —
  // asset tag/warehouse/least-count are fixed once registered).
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedScale = signal<ScaleResponse | null>(null);
  protected readonly editMode = signal(false);
  protected readonly saving = signal(false);

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  protected readonly columns: DataGridColumn<ScaleResponse>[] = [
    {
      field: 'asset_tag',
      header: 'Asset Tag',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openDetails(row),
    },
    {
      field: 'warehouse_id',
      header: 'Warehouse',
      sortable: true,
      valueFormatter: (value) => this.warehouseNameById().get(value as string) ?? (value as string),
    },
    { field: 'least_count_grams', header: 'Least Count (g)', sortable: true },
    { field: 'certificate_expiry_date', header: 'Certificate Expiry', sortable: true },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: FeatureScales.STATUS_SEVERITY },
    },
  ];

  protected readonly registerForm = this.fb.group({
    warehouse_id: ['', [Validators.required]],
    asset_tag: ['', [Validators.required]],
    make: [''],
    model: [''],
    least_count_grams: [
      10,
      [Validators.required, Validators.min(1), Validators.max(MAX_LEAST_COUNT_GRAMS)],
    ],
    certificate_ref: ['', [Validators.required]],
    certificate_expiry_date: this.fb.control<Date | null>(null, [Validators.required]),
  });

  /** Blob ref set by `<lpg-document-upload>` once the certificate is stored
   * — reuses the same generic attachment endpoint every other compliance
   * upload goes through (`DocumentService.uploadAttachment`, same as
   * `feature-drivers.ts`'s `licenceUploader`). */
  protected readonly certificateUploader = (file: File): Observable<{ blobRef: string }> =>
    this.documentService.uploadAttachment(file).pipe(map((r) => ({ blobRef: r.blob_ref })));

  protected readonly editForm = this.fb.group({
    certificate_ref: ['', [Validators.required]],
    certificate_expiry_date: this.fb.control<Date | null>(null, [Validators.required]),
  });

  protected readonly fieldMessages = {
    warehouse_id: { required: 'Select a warehouse.' },
    asset_tag: { required: 'Asset tag is required.' },
    least_count_grams: {
      required: 'Enter the scale’s least count.',
      min: 'Least count must be at least 1g.',
      max: `MDG 2022 requires a least count of ${MAX_LEAST_COUNT_GRAMS}g or finer.`,
    },
    certificate_ref: { required: 'Upload the calibration certificate.' },
    certificate_expiry_date: { required: 'Certificate expiry date is required.' },
  };

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadWarehouses();
    this.loadScales();
  }

  protected loadWarehouses(): void {
    this.warehouseService.listWarehouses().subscribe({
      next: (warehouses) => this.warehouses.set(warehouses),
      error: () => this.errorMessage.set('Failed to load warehouses.'),
    });
  }

  protected loadScales(): void {
    this.loading.set(true);
    const filter = this.expiryFilter();
    this.weighmentService
      .listScales({ expiry: filter === 'all' ? undefined : filter, limit: 200 })
      .subscribe({
        next: (page) => {
          this.scales.set(page.items);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected onExpiryFilterChange(value: 'all' | 'expiring' | 'expired'): void {
    this.expiryFilter.set(value);
    this.loadScales();
  }

  protected openRegisterModal(): void {
    this.registerForm.reset({
      warehouse_id: this.warehouses().length > 0 ? this.warehouses()[0].id : '',
      asset_tag: '',
      make: '',
      model: '',
      least_count_grams: 10,
      certificate_ref: '',
      certificate_expiry_date: null,
    });
    this.showRegisterModal.set(true);
  }

  protected onCertificateUploaded(event: { blobRef: string }): void {
    this.registerForm.controls.certificate_ref.setValue(event.blobRef);
    this.registerForm.controls.certificate_ref.markAsTouched();
  }

  protected onCertificateCleared(): void {
    this.registerForm.controls.certificate_ref.setValue('');
  }

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    const val = this.registerForm.getRawValue();
    this.loading.set(true);
    this.weighmentService
      .registerScale({
        warehouse_id: val.warehouse_id,
        asset_tag: val.asset_tag,
        make: val.make || null,
        model: val.model || null,
        least_count_grams: val.least_count_grams,
        certificate_ref: val.certificate_ref,
        certificate_expiry_date: formatDateForApi(val.certificate_expiry_date) ?? '',
      })
      .subscribe({
        next: () => {
          this.showRegisterModal.set(false);
          this.loadScales();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected openDetails(scale: ScaleResponse): void {
    this.selectedScale.set(scale);
    this.editMode.set(false);
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
  }

  protected startRecalibrate(): void {
    this.editForm.reset({ certificate_ref: '', certificate_expiry_date: null });
    this.editMode.set(true);
  }

  protected cancelEdit(): void {
    this.editMode.set(false);
  }

  protected onEditCertificateUploaded(event: { blobRef: string }): void {
    this.editForm.controls.certificate_ref.setValue(event.blobRef);
    this.editForm.controls.certificate_ref.markAsTouched();
  }

  protected onEditCertificateCleared(): void {
    this.editForm.controls.certificate_ref.setValue('');
  }

  protected saveRecalibration(): void {
    const scale = this.selectedScale();
    if (!scale || this.editForm.invalid) return;

    const val = this.editForm.getRawValue();
    this.saving.set(true);
    this.weighmentService
      .replaceScaleCertificate(scale.id, {
        certificate_ref: val.certificate_ref,
        certificate_expiry_date: formatDateForApi(val.certificate_expiry_date) ?? '',
      })
      .subscribe({
        next: (updated) => {
          this.selectedScale.set(updated);
          this.editMode.set(false);
          this.saving.set(false);
          this.messageService.add({
            severity: 'success',
            summary: 'Success',
            detail: 'Scale recalibrated.',
          });
          this.loadScales();
        },
        error: (err) => {
          this.saving.set(false);
          this.messageService.add({
            severity: 'error',
            summary: 'Error',
            detail: errorMessageFor(err),
          });
        },
      });
  }

  protected toggleStatus(): void {
    const scale = this.selectedScale();
    if (!scale) return;
    const newStatus = scale.status === 'active' ? 'inactive' : 'active';
    this.saving.set(true);
    this.weighmentService.setScaleStatus(scale.id, newStatus).subscribe({
      next: (updated) => {
        this.selectedScale.set(updated);
        this.saving.set(false);
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: `Scale marked ${newStatus}.`,
        });
        this.loadScales();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(err),
        });
      },
    });
  }

}
