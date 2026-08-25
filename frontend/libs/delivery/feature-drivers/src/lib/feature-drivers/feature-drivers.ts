import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
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
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin, type Observable } from 'rxjs';
import { KeyboardShortcutsService } from '@lpg/shared/util';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  StatusChipCell,
  type ChipSeverity,
  toSentenceCase,
} from '@lpg/shared/ui';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { MessageService } from 'primeng/api';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { DatePicker } from 'primeng/datepicker';
import {
  DeliveryService,
  AdminBranchService,
  AdminEmployeeService,
  type AppError,
  type BranchResponse,
  type DriverResponse,
  type EmployeeResponse,
} from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_EMPLOYEE_CODE':
      return 'A driver with this employee code already exists.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

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
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    IconField,
    InputIcon,
    Message,
    Select,
    Tag,
    DatePicker,
    DataGridComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-drivers.html',
  styleUrl: './feature-drivers.css',
})
export class FeatureDrivers implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly deliveryService = inject(DeliveryService);
  private readonly branchService = inject(AdminBranchService);
  private readonly employeeService = inject(AdminEmployeeService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly messageService = inject(MessageService);

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
    license_expiry_date: [''],
  });

  protected readonly editForm = this.fb.group({
    employee_id: ['', [Validators.required]],
    branch_id: ['', [Validators.required]],
    license_number: ['', [Validators.required]],
    license_expiry_date: this.fb.control<Date | null>(null),
    status: ['active', [Validators.required]],
  });

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
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


    const unregisterNew = this.keyboardShortcuts.register({
      key: 'n',
      alt: true,
      description: 'Register new driver',
      handler: () => {
        if (!this.showRegisterModal()) {
          this.openRegisterModal();
        }
      }
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
      unregisterNew();
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
      license_expiry_date: '',
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

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) return;

    const val = this.registerForm.getRawValue();
    this.loading.set(true);

    this.deliveryService
      .registerDriver({
        branch_id: val.branch_id,
        employee_id: val.employee_id,
        license_number: val.license_number,
        license_expiry_date: formatDateForApi(val.license_expiry_date),
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
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
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
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Driver updated.' });
        this.loadDrivers();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
      },
    });
  }
}
