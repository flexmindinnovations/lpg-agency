import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { KeyboardShortcutsService } from '@lpg/shared/util';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  StatusChipCell,
} from '@lpg/shared/ui';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
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

  protected readonly drivers = signal<DriverResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly employees = signal<(EmployeeResponse & { _displayName?: string })[]>([]);
  protected readonly selectedDriver = signal<DriverResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly errorMessage = signal<string | null>(null);

  // Modal Visibility Signals
  protected readonly showRegisterModal = signal(false);
  protected readonly showUpdateStatusModal = signal(false);

  // PrimeNG's Dialog has no built-in "return focus to trigger" behaviour —
  // matches `apps/dashboard/src/app/home/home.ts`'s documented pattern. The
  // Update Status dialog is opened via grid row selection, not a button, so
  // it has no natural focus-restore target and is intentionally left as-is.
  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  // Column definitions for drivers data grid
  protected readonly columns: DataGridColumn<DriverResponse>[] = [
    {
      field: 'employee_id',
      header: 'Employee ID',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openStatusModal(row),
    },
    { field: 'license_number', header: 'License Number', sortable: true },
    { field: 'license_expiry_date', header: 'License Expiry', sortable: true },
    { field: 'status', header: 'Status', sortable: true, cellRenderer: StatusChipCell },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    employee_id: ['', [Validators.required]],
    license_number: ['', [Validators.required]],
    license_expiry_date: [''],
  });

  protected readonly statusForm = this.fb.group({
    status: ['active', [Validators.required]],
  });

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  protected get updateStatusModalVisible(): boolean {
    return this.showUpdateStatusModal();
  }
  protected set updateStatusModalVisible(value: boolean) {
    this.showUpdateStatusModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
    this.loadDrivers();


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

    let expiryDateString: string | undefined = undefined;
    if (val.license_expiry_date) {
      const dateObj = new Date(val.license_expiry_date);
      const year = dateObj.getFullYear();
      const month = String(dateObj.getMonth() + 1).padStart(2, '0');
      const day = String(dateObj.getDate()).padStart(2, '0');
      expiryDateString = `${year}-${month}-${day}`;
    }

    this.deliveryService
      .registerDriver({
        branch_id: val.branch_id,
        employee_id: val.employee_id,
        license_number: val.license_number,
        license_expiry_date: expiryDateString,
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

  protected openStatusModal(driver: DriverResponse): void {
    this.selectedDriver.set(driver);
    this.statusForm.patchValue({ status: driver.status });
    this.showUpdateStatusModal.set(true);
  }

  protected onSubmitStatus(): void {
    const driver = this.selectedDriver();
    if (!driver || this.statusForm.invalid) return;

    const newStatus = this.statusForm.getRawValue().status;
    this.loading.set(true);
    this.deliveryService.updateDriverStatus(driver.id, newStatus).subscribe({
      next: () => {
        this.showUpdateStatusModal.set(false);
        this.loadDrivers();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }
}

