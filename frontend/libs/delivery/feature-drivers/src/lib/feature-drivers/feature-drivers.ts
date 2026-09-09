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
import { KeyboardShortcutsService } from '@lpg/shared/util';
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
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { DatePicker } from 'primeng/datepicker';
import {
  DeliveryService,
  DocumentService,
  AdminBranchService,
  AdminEmployeeService,
  NotifyService,
  errorMessageFor,
  type BranchResponse,
  type DriverResponse,
  type EmployeeResponse,
  type RecognizeComplianceDocumentResponse,
} from '@lpg/shared/data-access';

/** `dd-mm-yyyy`-picker value → `yyyy-mm-dd` API string, or `undefined` for
 * an empty/cleared field. Shared by Register and Edit — both post through
 * the same date-shaped fields. */
function formatDateForApi(value: unknown): string | undefined {
  if (!value) return undefined;
  const dateObj = new Date(value as string | number | Date);
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

@Component({
  selector: 'lpg-feature-drivers',
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
  templateUrl: './feature-drivers.html',
  styleUrl: './feature-drivers.css',
})
export class FeatureDrivers implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly deliveryService = inject(DeliveryService);
  private readonly documentService = inject(DocumentService);
  private readonly branchService = inject(AdminBranchService);
  private readonly employeeService = inject(AdminEmployeeService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly notify = inject(NotifyService);

  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    active: 'success',
    on_leave: 'warn',
    inactive: 'secondary',
  };

  protected readonly statusOptions = [
    { label: 'Active', value: 'active' },
    { label: 'On Leave', value: 'on_leave' },
    { label: 'Inactive', value: 'inactive' },
  ];

  protected readonly toSentenceCase = toSentenceCase;

  protected statusSeverity(status: string): ChipSeverity {
    return FeatureDrivers.STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected readonly drivers = signal<DriverResponse[]>([]);

  // Expiry filter (list page, above the grid) — "missing" and "expiring"/
  // "expired" both need to know which drivers' documents look like that,
  // computed client-side from a full compliance-document fetch since the
  // list endpoint has no owner-missing-required-doc query of its own.
  protected readonly expiryFilterOptions = [
    { label: 'All drivers', value: 'all' },
    { label: 'Documents expiring ≤30d', value: 'expiring' },
    { label: 'Documents expired', value: 'expired' },
    { label: 'Missing licence on file', value: 'missing' },
  ];
  protected readonly expiryFilter = signal<'all' | 'expiring' | 'expired' | 'missing'>('all');
  private readonly driverComplianceFlags = signal<
    Map<string, { expiring: boolean; expired: boolean; hasRequired: boolean }>
  >(new Map());

  protected readonly filteredDrivers = computed(() => {
    const filter = this.expiryFilter();
    const all = this.drivers();
    if (filter === 'all') return all;
    const flags = this.driverComplianceFlags();
    return all.filter((d) => {
      const f = flags.get(d.id);
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
  protected readonly employees = signal<(EmployeeResponse & { _displayName?: string })[]>([]);
  // Unscoped (all branches) — feeds the grid's Employee Code lookup, distinct
  // from `employees` above which is branch-scoped for the register modal's
  // dropdown and may not cover every driver currently shown in the grid.
  protected readonly allEmployees = signal<EmployeeResponse[]>([]);

  protected readonly employeeCodeById = computed(() => {
    const map = new Map<string, string>();
    for (const e of this.allEmployees()) map.set(e.id, e.employee_code);
    return map;
  });

  // Unscoped + display-name-mapped — feeds the Edit form's Employee
  // dropdown, distinct from `employees` (branch-scoped, for Register) since
  // reassignment should be able to pick any employee, not just ones in
  // whatever branch happened to be selected first.
  protected readonly allEmployeesDisplay = computed(() =>
    this.allEmployees().map((e) => ({
      ...e,
      _displayName: `${e.first_name} ${e.last_name} (${e.employee_code})`,
    })),
  );

  protected readonly branchNameById = computed(() => {
    const map = new Map<string, string>();
    for (const b of this.branches()) map.set(b.id, b.name);
    return map;
  });
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly errorMessage = signal<string | null>(null);

  // Modal Visibility Signals
  protected readonly showRegisterModal = signal(false);

  // Details drawer — view mode shows the driver's current data (with an
  // Edit button, gated by RBAC below), edit mode swaps in a form covering
  // every field. Employee/Branch, License, and Status each go through
  // their own backend endpoint (reassignment is a structural identity
  // change, not a plain field edit — see `Driver.reassign` on the
  // backend), so saveEdit() only calls whichever endpoint(s) actually
  // changed.
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedDriver = signal<DriverResponse | null>(null);
  protected readonly editMode = signal(false);
  protected readonly saving = signal(false);

  // Compliance-documents panel (drawer) — driver-specific doc types + the
  // owner-scoped list, reloaded whenever the drawer opens or a document is
  // added/replaced/verified.
  protected readonly driverDocTypeOptions = [
    { label: 'Driving licence', value: 'driving_licence' },
    { label: 'DL hazmat endorsement', value: 'dl_hazmat_endorsement' },
    { label: 'TREM card', value: 'trem_card' },
    { label: 'Driver training certificate', value: 'driver_training_certificate' },
  ];
  protected readonly driverDocuments = signal<ComplianceDocumentItem[]>([]);
  protected readonly driverDocumentsLoading = signal(false);

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  // Column definitions for drivers data grid
  protected readonly columns: DataGridColumn<DriverResponse>[] = [
    {
      field: 'employee_id',
      header: 'Employee Code',
      sortable: true,
      filterable: true,
      valueFormatter: (value) => this.employeeCodeById().get(value as string) ?? (value as string),
      onLinkClick: (row) => this.openDetails(row),
    },
    { field: 'license_number', header: 'License Number', sortable: true },
    { field: 'license_expiry_date', header: 'License Expiry', sortable: true },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: FeatureDrivers.STATUS_SEVERITY },
    },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    employee_id: ['', [Validators.required]],
    license_number: ['', [Validators.required]],
    license_expiry_date: this.fb.control<Date | null>(null, [Validators.required]),
    licence_document_ref: ['', [Validators.required]],
  });

  /** Blob ref set by `<lpg-document-upload>` once the licence scan is stored. */
  protected readonly licenceUploader = (file: File): Observable<{ blobRef: string }> =>
    this.documentService.uploadAttachment(file).pipe(map((r) => ({ blobRef: r.blob_ref })));
  protected readonly licenceRecognizer = (
    blobRef: string,
  ): Observable<RecognizeComplianceDocumentResponse> =>
    this.documentService.recognize(blobRef, 'driving_licence');

  protected readonly editForm = this.fb.group({
    employee_id: ['', [Validators.required]],
    branch_id: ['', [Validators.required]],
    license_number: ['', [Validators.required]],
    license_expiry_date: this.fb.control<Date | null>(null),
    status: ['active', [Validators.required]],
  });

  /** Validator-key → message, shared by the register and edit forms. */
  protected readonly fieldMessages = {
    branch_id: { required: 'Select a branch.' },
    employee_id: { required: 'Select an employee.' },
    license_number: { required: 'License number is required.' },
    license_expiry_date: { required: 'License expiry date is required.' },
    licence_document_ref: { required: 'Upload a scan of the driving licence.' },
    status: { required: 'Select a duty status.' },
  };

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
    this.loadDriverComplianceFlags();
    this.loading.set(true);
    // Load employees before the first `loadDrivers()` call, not in
    // parallel with it: the grid's Employee Code column resolves through
    // AG Grid's `valueFormatter`, which only runs when row data is (re)set
    // into the grid — it doesn't re-run reactively when `allEmployees`
    // (and therefore `employeeCodeById`) changes afterward. Firing both
    // requests at once raced the two responses — whichever landed first
    // decided whether that column showed the code or the raw employee_id
    // UUID, until something else (search, a refresh) re-set the rows.
    this.employeeService.listEmployees({}).subscribe({
      next: (page) => {
        this.allEmployees.set(page.items);
        this.loadDrivers();
      },
      error: () => this.loadDrivers(),
    });


    const unregisterSearch = this.keyboardShortcuts.register({
      key: '/',
      description: 'Focus driver search',
      handler: () => {
        const searchInput = document.getElementById('driver-search-input');
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

  protected loadEmployees(branchId?: string): void {
    this.employeeService.listEmployees({ branch_id: branchId }).subscribe({
      next: (page) => {
        const mapped = page.items.map(e => ({
          ...e,
          _displayName: `${e.first_name} ${e.last_name} (${e.employee_code})`
        }));
        this.employees.set(mapped);
      },
      error: () => this.errorMessage.set('Failed to load employees.'),
    });
  }

  protected loadDrivers(): void {
    this.loading.set(true);
    this.deliveryService.listDrivers(0, 100, this.searchQuery() || undefined).subscribe({
      next: (page) => {
        this.drivers.set(page.items);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  /** Feeds the Expiry filter — one tenant-wide fetch of every driver
   * document, reduced to a per-driver flag map client-side (the list
   * endpoint has no "missing required doc" query of its own). */
  protected loadDriverComplianceFlags(): void {
    this.documentService.listComplianceDocuments({ owner_type: 'driver', limit: 500 }).subscribe({
      next: (res) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const map = new Map<string, { expiring: boolean; expired: boolean; hasRequired: boolean }>();
        for (const doc of res.items) {
          const entry = map.get(doc.owner_id) ?? { expiring: false, expired: false, hasRequired: false };
          if (doc.doc_type === 'driving_licence') entry.hasRequired = true;
          if (doc.expiry_date) {
            const diffDays = Math.round(
              (new Date(doc.expiry_date).getTime() - today.getTime()) / 86_400_000,
            );
            if (diffDays < 0) entry.expired = true;
            else if (diffDays <= 30) entry.expiring = true;
          }
          map.set(doc.owner_id, entry);
        }
        this.driverComplianceFlags.set(map);
      },
    });
  }

  protected onSearch(event: Event): void {
    const query = (event.target as HTMLInputElement).value;
    this.searchQuery.set(query);
    this.loadDrivers();
  }

  protected openRegisterModal(): void {
    const initialBranchId = this.branches().length > 0 ? this.branches()[0].id : '';
    this.registerForm.reset({
      branch_id: initialBranchId,
      employee_id: '',
      license_number: '',
      license_expiry_date: null,
      licence_document_ref: '',
    });

    if (initialBranchId) {
      this.loadEmployees(initialBranchId);
    } else {
      this.loadEmployees();
    }

    // Refresh employees when branch changes
    this.registerForm.controls.branch_id.valueChanges.subscribe(val => {
      if (val) this.loadEmployees(val);
    });

    this.showRegisterModal.set(true);
  }

  /** `<lpg-document-upload>` stored the licence scan — keep the ref. */
  protected onLicenceUploaded(event: { blobRef: string }): void {
    this.registerForm.controls.licence_document_ref.setValue(event.blobRef);
    this.registerForm.controls.licence_document_ref.markAsTouched();
  }

  protected onLicenceCleared(): void {
    this.registerForm.controls.licence_document_ref.setValue('');
  }

  /** OCR "second pass" result — pre-fill number + expiry, still editable. */
  protected onLicenceRecognized(result: unknown): void {
    const dl = result as RecognizeComplianceDocumentResponse;
    if (dl.document_number) {
      this.registerForm.controls.license_number.setValue(dl.document_number);
    }
    const expiry = dl.transport_valid_till ?? dl.valid_till;
    if (expiry) {
      this.registerForm.controls.license_expiry_date.setValue(new Date(expiry));
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
      .registerDriver({
        branch_id: val.branch_id,
        employee_id: val.employee_id,
        license_number: val.license_number,
        license_expiry_date: formatDateForApi(val.license_expiry_date) ?? '',
        licence_document_ref: val.licence_document_ref,
      })
      .subscribe({
        next: () => {
          this.showRegisterModal.set(false);
          this.loadDrivers();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected openDetails(driver: DriverResponse): void {
    this.selectedDriver.set(driver);
    this.editMode.set(false);
    this.showDetailDrawer.set(true);
    this.loadDriverDocuments(driver.id);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
  }

  protected loadDriverDocuments(driverId: string): void {
    this.driverDocumentsLoading.set(true);
    this.documentService.listDriverDocuments(driverId).subscribe({
      next: (res) => {
        this.driverDocuments.set(res.items);
        this.driverDocumentsLoading.set(false);
      },
      error: () => {
        this.driverDocuments.set([]);
        this.driverDocumentsLoading.set(false);
      },
    });
  }

  /** Bound per-driver in the template — `<lpg-compliance-documents-panel>`
   * calls this with the new document's fields once its inline form submits. */
  protected addDriverDocument(driver: DriverResponse) {
    return (cmd: AddComplianceDocumentCmd) => this.documentService.addDriverDocument(driver.id, cmd);
  }

  /** Replace/verify are owner-agnostic on the backend — no driver id needed. */
  protected readonly replaceComplianceDocument = (
    documentId: string,
    cmd: ReplaceComplianceDocumentCmd,
  ) => this.documentService.replace(documentId, cmd);

  protected readonly verifyComplianceDocument = (
    documentId: string,
    cmd: VerifyComplianceDocumentCmd,
  ) => this.documentService.verify(documentId, cmd);

  protected onDriverDocumentsChanged(): void {
    const driver = this.selectedDriver();
    if (driver) this.loadDriverDocuments(driver.id);
    this.loadDriverComplianceFlags();
    this.notify.success('Compliance documents updated.');
  }

  protected startEdit(): void {
    const driver = this.selectedDriver();
    if (!driver) return;
    this.editForm.reset({
      employee_id: driver.employee_id,
      branch_id: driver.branch_id,
      license_number: driver.license_number,
      license_expiry_date: driver.license_expiry_date ? new Date(driver.license_expiry_date) : null,
      status: driver.status,
    });
    this.editMode.set(true);
  }

  protected cancelEdit(): void {
    this.editMode.set(false);
  }

  /** Calls whichever of the three backend endpoints (assignment, license,
   * status) the changed fields actually need — there's no single "update
   * everything" endpoint, so an unchanged field isn't sent, both to avoid a
   * pointless PATCH and to keep the audit trail free of no-op entries. */
  protected saveEdit(): void {
    const driver = this.selectedDriver();
    if (!driver || this.editForm.invalid) return;

    const val = this.editForm.getRawValue();
    const newExpiry = formatDateForApi(val.license_expiry_date) ?? null;
    const assignmentChanged =
      val.employee_id !== driver.employee_id || val.branch_id !== driver.branch_id;
    const licenseChanged =
      val.license_number !== driver.license_number || newExpiry !== driver.license_expiry_date;
    const statusChanged = val.status !== driver.status;

    if (!assignmentChanged && !licenseChanged && !statusChanged) {
      this.editMode.set(false);
      return;
    }

    const requests: Observable<DriverResponse>[] = [];
    if (assignmentChanged) {
      requests.push(
        this.deliveryService.updateDriverAssignment(driver.id, {
          employee_id: val.employee_id,
          branch_id: val.branch_id,
        }),
      );
    }
    if (licenseChanged) {
      requests.push(
        this.deliveryService.updateDriverLicense(driver.id, {
          license_number: val.license_number,
          license_expiry_date: newExpiry,
        }),
      );
    }
    if (statusChanged) {
      requests.push(this.deliveryService.updateDriverStatus(driver.id, val.status));
    }

    this.saving.set(true);
    forkJoin(requests).subscribe({
      next: (results) => {
        this.selectedDriver.set(results[results.length - 1]);
        this.editMode.set(false);
        this.saving.set(false);
        this.notify.success('Driver updated.');
        this.loadDrivers();
      },
      error: () => this.saving.set(false),
    });
  }
}
