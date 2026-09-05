import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
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
import { KeyboardShortcutsService } from '@lpg/shared/util';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { ConfirmationService } from 'primeng/api';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import {
  AdminEmployeeService,
  AdminBranchService,
  type AppError,
  type BranchResponse,
  type EmployeeResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  type DataGridColumn,
  FormFieldComponent,
  HasPermissionDirective,
  PageHeaderComponent,
  StatusChipCell,
  type ChipSeverity,
  toSentenceCase,
} from '@lpg/shared/ui';
import { ROLE_OPTIONS } from '../employee-role-options';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_EMPLOYEE':
      return 'An employee with this information already exists.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    case 'RESOURCE_NOT_FOUND':
      return 'That employee could not be found.';
    default:
      return 'Something went wrong. Please try again.';
  }
}

const STATUS_SEVERITY: Record<string, ChipSeverity> = {
  active: 'success',
  on_leave: 'warn',
  inactive: 'secondary',
};

@Component({
  selector: 'lib-feature-employees',
  standalone: true,
  imports: [
    PageHeaderComponent,
    HeaderPortalDirective,
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    Message,
    Select,
    Tag,
    DataGridComponent,
    HasPermissionDirective,
    IconField,
    InputIcon,
    FormFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-employees.html',
  styleUrl: './feature-employees.css',
})
export class FeatureEmployees implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly employeeService = inject(AdminEmployeeService);
  private readonly branchService = inject(AdminBranchService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly confirmationService = inject(ConfirmationService);

  protected readonly employees = signal<EmployeeResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly showRegisterModal = signal(false);
  protected readonly showDetailsDrawer = signal(false);
  protected readonly showEditDrawer = signal(false);
  protected readonly selectedEmployee = signal<EmployeeResponse | null>(null);

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  protected readonly roleOptions = ROLE_OPTIONS;
  protected readonly toSentenceCase = toSentenceCase;

  /** Validator-key → message, shared by the register and edit forms. */
  protected readonly fieldMessages = {
    branch_id: { required: 'Select a branch.' },
    first_name: { required: 'First name is required.' },
    last_name: { required: 'Last name is required.' },
    phone_number: { required: 'Phone number is required.' },
    email: { email: 'Enter a valid email address.' },
    role: { required: 'Select a role.' },
  };

  protected readonly branchNameById = computed(() => {
    const map = new Map<string, string>();
    for (const b of this.branches()) map.set(b.id, b.name);
    return map;
  });

  protected readonly canDeactivate = computed(() => {
    const status = this.selectedEmployee()?.status;
    return status === 'active' || status === 'on_leave';
  });

  protected statusSeverity(status: string): ChipSeverity {
    return STATUS_SEVERITY[status] ?? 'secondary';
  }

  // Column definitions for employees data grid
  protected readonly columns: DataGridColumn<EmployeeResponse>[] = [
    {
      field: 'employee_code',
      header: 'Employee Code',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openDetailsDrawer(row),
    },
    { field: 'first_name', header: 'First Name', sortable: true },
    { field: 'last_name', header: 'Last Name', sortable: true },
    { field: 'role', header: 'Role', sortable: true, cellRenderer: StatusChipCell },
    { field: 'status', header: 'Status', sortable: true, cellRenderer: StatusChipCell },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    first_name: ['', [Validators.required]],
    last_name: ['', [Validators.required]],
    phone_number: ['', [Validators.required]],
    email: ['', [Validators.email]],
    role: ['', [Validators.required]],
  });

  protected readonly editForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    first_name: ['', [Validators.required]],
    last_name: ['', [Validators.required]],
    phone_number: ['', [Validators.required]],
    email: ['', [Validators.email]],
    role: ['', [Validators.required]],
  });

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
    this.loadEmployees();

    const unregisterNew = this.keyboardShortcuts.register({
      key: 'n',
      alt: true,
      description: 'Register new employee',
      handler: () => {
        if (!this.showRegisterModal()) {
          this.openRegisterModal();
        }
      },
    });

    const unregisterSearch = this.keyboardShortcuts.register({
      key: '/',
      description: 'Focus employee search',
      handler: () => {
        const searchInput = document.getElementById('employee-search-input');
        if (searchInput) {
          searchInput.focus();
        }
      },
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

  protected loadEmployees(): void {
    this.loading.set(true);
    this.employeeService.listEmployees({ skip: 0, limit: 100, search: this.searchQuery() || undefined }).subscribe({
      next: (page) => {
        this.employees.set(page.items);
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
    this.loadEmployees();
  }

  protected openRegisterModal(): void {
    this.registerForm.reset({
      branch_id: this.branches().length > 0 ? this.branches()[0].id : '',
      first_name: '',
      last_name: '',
      phone_number: '',
      email: '',
      role: '',
    });
    this.showRegisterModal.set(true);
  }

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) return;

    const val = this.registerForm.getRawValue();
    this.loading.set(true);
    this.employeeService
      .registerEmployee({
        branch_id: val.branch_id,
        first_name: val.first_name,
        last_name: val.last_name,
        phone_number: val.phone_number,
        email: val.email || undefined,
        role: val.role,
      })
      .subscribe({
        next: () => {
          this.showRegisterModal.set(false);
          this.loading.set(false);
          this.loadEmployees();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Details drawer
  // ---------------------------------------------------------------------------

  protected openDetailsDrawer(employee: EmployeeResponse): void {
    this.errorMessage.set(null);
    this.selectedEmployee.set(employee);
    this.showDetailsDrawer.set(true);
  }

  protected openEditDrawer(): void {
    const employee = this.selectedEmployee();
    if (!employee) return;
    this.editForm.reset({
      branch_id: employee.branch_id,
      first_name: employee.first_name,
      last_name: employee.last_name,
      phone_number: employee.phone_number,
      email: employee.email ?? '',
      role: employee.role,
    });
    this.showEditDrawer.set(true);
  }

  protected onSubmitEdit(): void {
    const employee = this.selectedEmployee();
    if (!employee || this.editForm.invalid) return;

    const val = this.editForm.getRawValue();
    this.loading.set(true);
    this.employeeService
      .updateEmployee(employee.id, {
        branch_id: val.branch_id,
        first_name: val.first_name,
        last_name: val.last_name,
        phone_number: val.phone_number,
        email: val.email || undefined,
        role: val.role,
      })
      .subscribe({
        next: (updated) => {
          this.selectedEmployee.set(updated);
          this.showEditDrawer.set(false);
          this.loading.set(false);
          this.loadEmployees();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected confirmDeactivate(): void {
    const employee = this.selectedEmployee();
    if (!employee) return;
    this.confirmationService.confirm({
      header: 'Deactivate Employee',
      message: `Deactivate ${employee.first_name} ${employee.last_name}? They will no longer be able to sign in.`,
      acceptLabel: 'Deactivate',
      rejectLabel: 'Cancel',
      acceptButtonProps: { severity: 'danger' },
      accept: () => this.deactivate(employee.id),
    });
  }

  private deactivate(employeeId: string): void {
    this.loading.set(true);
    this.employeeService.changeEmployeeStatus(employeeId, { status: 'inactive' }).subscribe({
      next: (updated) => {
        this.selectedEmployee.set(updated);
        this.loading.set(false);
        this.loadEmployees();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }
}
