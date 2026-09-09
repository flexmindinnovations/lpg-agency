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
  DestroyRef,
} from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin, map, type Observable } from 'rxjs';
import {
  ComplianceDocumentsPanel,
  type AddComplianceDocumentCmd,
  type ComplianceDocumentItem,
  type ReplaceComplianceDocumentCmd,
  type VerifyComplianceDocumentCmd,
  DataGridComponent,
  type DataGridColumn,
  DocumentUploadComponent,
  FormFieldComponent,
  HasPermissionDirective,
  StatusChipCell,
  type ChipSeverity,
  toSentenceCase,
} from '@lpg/shared/ui';
import { KeyboardShortcutsService } from '@lpg/shared/util';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { Tag } from 'primeng/tag';
import {
  AdminBranchService,
  DeliveryService,
  DocumentService,
  NotifyService,
  errorMessageFor,
  type BranchResponse,
  type RecognizeComplianceDocumentResponse,
  type VehicleResponse,
} from '@lpg/shared/data-access';

/** `dd-mm-yyyy`-picker value → `yyyy-mm-dd` API string, or `undefined`. */
function formatDateForApi(value: unknown): string | undefined {
  if (!value) return undefined;
  const d = new Date(value as string | number | Date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}

@Component({
  selector: 'lpg-feature-vehicles',
  standalone: true,
  imports: [HeaderTitlePortalDirective,
    ReactiveFormsModule,
    FormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
    Message,
    Select,
    Tag,
    DatePicker,
    DataGridComponent,
    FormFieldComponent,
    DocumentUploadComponent,
    HasPermissionDirective,
    ComplianceDocumentsPanel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-vehicles.html',
  styleUrl: './feature-vehicles.css',
})
export class FeatureVehicles implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly deliveryService = inject(DeliveryService);
  private readonly documentService = inject(DocumentService);
  private readonly branchService = inject(AdminBranchService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly notify = inject(NotifyService);

  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    active: 'success',
    maintenance: 'warn',
    inactive: 'secondary',
  };

  protected readonly statusOptions = [
    { label: 'Active', value: 'active' },
    { label: 'Maintenance', value: 'maintenance' },
    { label: 'Inactive', value: 'inactive' },
  ];

  protected readonly toSentenceCase = toSentenceCase;

  protected statusSeverity(status: string): ChipSeverity {
    return FeatureVehicles.STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected readonly vehicles = signal<VehicleResponse[]>([]);

  // Expiry filter (list page, above the grid) — mirrors FeatureDrivers'
  // client-side filter, computed from a full compliance-document fetch
  // since the list endpoint has no owner-missing-required-doc query.
  protected readonly expiryFilterOptions = [
    { label: 'All vehicles', value: 'all' },
    { label: 'Documents expiring ≤30d', value: 'expiring' },
    { label: 'Documents expired', value: 'expired' },
    { label: 'Missing RC on file', value: 'missing' },
  ];
  protected readonly expiryFilter = signal<'all' | 'expiring' | 'expired' | 'missing'>('all');
  private readonly vehicleComplianceFlags = signal<
    Map<string, { expiring: boolean; expired: boolean; hasRequired: boolean }>
  >(new Map());

  protected readonly filteredVehicles = computed(() => {
    const filter = this.expiryFilter();
    const all = this.vehicles();
    if (filter === 'all') return all;
    const flags = this.vehicleComplianceFlags();
    return all.filter((v) => {
      const f = flags.get(v.id);
      switch (filter) {
        case 'expiring':
          return !!f?.expiring;
        case 'expired':
          return !!f?.expired;
        case 'missing':
          return !f?.hasRequired;
        default:
          return true;
      }
    });
  });

  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly errorMessage = signal<string | null>(null);

  // Modal Visibility Signals
  protected readonly showRegisterModal = signal(false);

  // Details drawer — view mode shows the vehicle's current data (with an
  // Edit button, gated by RBAC below), edit mode swaps in a form covering
  // every field: make/model/ownership/capacity go through the "details"
  // endpoint, status through its own — separate domain operations, so
  // saveEdit() only calls whichever endpoint(s) actually changed.
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedVehicle = signal<VehicleResponse | null>(null);
  protected readonly editMode = signal(false);
  protected readonly saving = signal(false);

  // Compliance-documents panel (drawer) — vehicle-specific doc types + the
  // owner-scoped list, reloaded whenever the drawer opens or a document is
  // added/replaced/verified.
  protected readonly vehicleDocTypeOptions = [
    { label: 'Registration certificate (RC)', value: 'vehicle_rc' },
    { label: 'Insurance', value: 'vehicle_insurance' },
    { label: 'Fitness certificate', value: 'vehicle_fitness' },
    { label: 'PUC certificate', value: 'vehicle_puc' },
    { label: 'PESO transport licence', value: 'peso_transport_licence' },
  ];
  protected readonly vehicleDocuments = signal<ComplianceDocumentItem[]>([]);
  protected readonly vehicleDocumentsLoading = signal(false);

  protected readonly ownershipOptions = [
    { label: 'Owned', value: 'owned' },
    { label: 'Third Party', value: 'third_party' },
    { label: 'Rental', value: 'rental' },
    { label: 'Gig', value: 'gig' },
  ];

  protected readonly editForm = this.fb.group({
    make: ['', [Validators.required]],
    model: ['', [Validators.required]],
    ownership_type: ['owned', [Validators.required]],
    capacity_units: [1, [Validators.required, Validators.min(1)]],
    status: ['active', [Validators.required]],
  });

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  // Column definitions for vehicles data grid
  protected readonly columns: DataGridColumn<VehicleResponse>[] = [
    {
      field: 'registration_number',
      header: 'Reg No.',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openDetails(row),
    },
    { field: 'make', header: 'Make', sortable: true },
    { field: 'model', header: 'Model', sortable: true },
    { field: 'ownership_type', header: 'Ownership', sortable: true, cellRenderer: StatusChipCell },
    { field: 'capacity_units', header: 'Capacity (Cylinders)', sortable: true },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: FeatureVehicles.STATUS_SEVERITY },
    },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    registration_number: ['', [Validators.required]],
    make: ['', [Validators.required]],
    model: ['', [Validators.required]],
    ownership_type: ['owned', [Validators.required]],
    capacity_units: [20, [Validators.required, Validators.min(1)]],
    rc_document_ref: ['', [Validators.required]],
    rc_expiry_date: this.fb.control<Date | null>(null, [Validators.required]),
  });

  /** Blob ref set by `<lpg-document-upload>` once the RC scan is stored. */
  protected readonly rcUploader = (file: File): Observable<{ blobRef: string }> =>
    this.documentService.uploadAttachment(file).pipe(map((r) => ({ blobRef: r.blob_ref })));
  protected readonly rcRecognizer = (
    blobRef: string,
  ): Observable<RecognizeComplianceDocumentResponse> =>
    this.documentService.recognize(blobRef, 'vehicle_rc');

  /** Validator-key → message, shared by the register and edit forms. */
  protected readonly fieldMessages = {
    branch_id: { required: 'Select a branch.' },
    registration_number: { required: 'Registration number is required.' },
    make: { required: 'Make is required.' },
    model: { required: 'Model is required.' },
    ownership_type: { required: 'Select an ownership type.' },
    capacity_units: { required: 'Enter a capacity.', min: 'Capacity must be at least 1.' },
    rc_document_ref: { required: 'Upload a scan of the registration certificate.' },
    rc_expiry_date: { required: 'RC validity date is required.' },
    status: { required: 'Select a status.' },
  };

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
    this.loadVehicles();
    this.loadVehicleComplianceFlags();


    const unregisterSearch = this.keyboardShortcuts.register({
      key: '/',
      description: 'Focus vehicle search',
      handler: () => {
        const searchInput = document.getElementById('vehicle-search-input');
        if (searchInput) {
          searchInput.focus();
        }
      }
    });

    this.destroyRef.onDestroy(() => {
      unregisterSearch();
    });
  }

  protected loadBranches(): void {
    this.branchService.listBranches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () => this.errorMessage.set('Failed to load branches.'),
    });
  }

  protected loadVehicles(): void {
    this.loading.set(true);
    this.deliveryService.listVehicles(0, 100, this.searchQuery() || undefined).subscribe({
      next: (page) => {
        this.vehicles.set(page.items);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  /** Feeds the Expiry filter — one tenant-wide fetch of every vehicle
   * document, reduced to a per-vehicle flag map client-side (the list
   * endpoint has no "missing required doc" query of its own). */
  protected loadVehicleComplianceFlags(): void {
    this.documentService.listComplianceDocuments({ owner_type: 'vehicle', limit: 500 }).subscribe({
      next: (res) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const map = new Map<string, { expiring: boolean; expired: boolean; hasRequired: boolean }>();
        for (const doc of res.items) {
          const entry = map.get(doc.owner_id) ?? { expiring: false, expired: false, hasRequired: false };
          if (doc.doc_type === 'vehicle_rc') entry.hasRequired = true;
          if (doc.expiry_date) {
            const diffDays = Math.round(
              (new Date(doc.expiry_date).getTime() - today.getTime()) / 86_400_000,
            );
            if (diffDays < 0) entry.expired = true;
            else if (diffDays <= 30) entry.expiring = true;
          }
          map.set(doc.owner_id, entry);
        }
        this.vehicleComplianceFlags.set(map);
      },
    });
  }

  protected onSearch(event: Event): void {
    const query = (event.target as HTMLInputElement).value;
    this.searchQuery.set(query);
    this.loadVehicles();
  }

  protected openRegisterModal(): void {
    this.registerForm.reset({
      branch_id: this.branches().length > 0 ? this.branches()[0].id : '',
      registration_number: '',
      make: '',
      model: '',
      ownership_type: 'owned',
      capacity_units: 20,
      rc_document_ref: '',
      rc_expiry_date: null,
    });
    this.showRegisterModal.set(true);
  }

  protected onRcUploaded(event: { blobRef: string }): void {
    this.registerForm.controls.rc_document_ref.setValue(event.blobRef);
    this.registerForm.controls.rc_document_ref.markAsTouched();
  }

  protected onRcCleared(): void {
    this.registerForm.controls.rc_document_ref.setValue('');
  }

  protected onRcRecognized(result: unknown): void {
    const rc = result as RecognizeComplianceDocumentResponse;
    if (rc.registration_number) {
      this.registerForm.controls.registration_number.setValue(rc.registration_number);
    }
    if (rc.fuel_type || rc.maker_model) {
      // Maker/model isn't a form field here — leave for the user, RC OCR of it
      // is low confidence anyway.
    }
    if (rc.valid_till) {
      this.registerForm.controls.rc_expiry_date.setValue(new Date(rc.valid_till));
    }
  }

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    const val = this.registerForm.getRawValue();
    this.loading.set(true);
    this.deliveryService
      .registerVehicle({
        branch_id: val.branch_id,
        registration_number: val.registration_number,
        make: val.make,
        model: val.model,
        ownership_type: val.ownership_type,
        capacity_units: val.capacity_units,
        rc_document_ref: val.rc_document_ref,
        rc_expiry_date: formatDateForApi(val.rc_expiry_date) ?? '',
      })
      .subscribe({
        next: () => {
          this.showRegisterModal.set(false);
          this.loadVehicles();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected openDetails(vehicle: VehicleResponse): void {
    this.selectedVehicle.set(vehicle);
    this.editMode.set(false);
    this.showDetailDrawer.set(true);
    this.loadVehicleDocuments(vehicle.id);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
  }

  protected loadVehicleDocuments(vehicleId: string): void {
    this.vehicleDocumentsLoading.set(true);
    this.documentService.listVehicleDocuments(vehicleId).subscribe({
      next: (res) => {
        this.vehicleDocuments.set(res.items);
        this.vehicleDocumentsLoading.set(false);
      },
      error: () => {
        this.vehicleDocuments.set([]);
        this.vehicleDocumentsLoading.set(false);
      },
    });
  }

  /** Bound per-vehicle in the template — `<lpg-compliance-documents-panel>`
   * calls this with the new document's fields once its inline form submits. */
  protected addVehicleDocument(vehicle: VehicleResponse) {
    return (cmd: AddComplianceDocumentCmd) => this.documentService.addVehicleDocument(vehicle.id, cmd);
  }

  /** Replace/verify are owner-agnostic on the backend — no vehicle id needed. */
  protected readonly replaceComplianceDocument = (
    documentId: string,
    cmd: ReplaceComplianceDocumentCmd,
  ) => this.documentService.replace(documentId, cmd);

  protected readonly verifyComplianceDocument = (
    documentId: string,
    cmd: VerifyComplianceDocumentCmd,
  ) => this.documentService.verify(documentId, cmd);

  protected onVehicleDocumentsChanged(): void {
    const vehicle = this.selectedVehicle();
    if (vehicle) this.loadVehicleDocuments(vehicle.id);
    this.loadVehicleComplianceFlags();
    this.notify.success('Compliance documents updated.');
  }

  protected startEdit(): void {
    const vehicle = this.selectedVehicle();
    if (!vehicle) return;
    this.editForm.reset({
      make: vehicle.make,
      model: vehicle.model,
      ownership_type: vehicle.ownership_type,
      capacity_units: vehicle.capacity_units,
      status: vehicle.status,
    });
    this.editMode.set(true);
  }

  protected cancelEdit(): void {
    this.editMode.set(false);
  }

  /** Calls whichever of the two backend endpoints (details, status) the
   * changed fields actually need — mirrors `FeatureDrivers.saveEdit()`. */
  protected saveEdit(): void {
    const vehicle = this.selectedVehicle();
    if (!vehicle || this.editForm.invalid) return;

    const val = this.editForm.getRawValue();
    const detailsChanged =
      val.make !== vehicle.make ||
      val.model !== vehicle.model ||
      val.ownership_type !== vehicle.ownership_type ||
      val.capacity_units !== vehicle.capacity_units;
    const statusChanged = val.status !== vehicle.status;

    if (!detailsChanged && !statusChanged) {
      this.editMode.set(false);
      return;
    }

    const requests: Observable<VehicleResponse>[] = [];
    if (detailsChanged) {
      requests.push(
        this.deliveryService.updateVehicleDetails(vehicle.id, {
          make: val.make,
          model: val.model,
          ownership_type: val.ownership_type,
          capacity_units: val.capacity_units,
        }),
      );
    }
    if (statusChanged) {
      requests.push(this.deliveryService.updateVehicleStatus(vehicle.id, val.status));
    }

    this.saving.set(true);
    forkJoin(requests).subscribe({
      next: (results) => {
        this.selectedVehicle.set(results[results.length - 1]);
        this.editMode.set(false);
        this.saving.set(false);
        this.notify.success('Vehicle updated.');
        this.loadVehicles();
      },
      error: () => this.saving.set(false),
    });
  }
}
