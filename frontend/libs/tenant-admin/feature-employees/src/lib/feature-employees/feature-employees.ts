import { HeaderPortalDirective } from '@lpg/shared/ui/app-shell';
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
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import {
  AdminEmployeeService,
  AdminBranchService,
  type AppError,
  type BranchResponse,
  type EmployeeResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_EMPLOYEE':
      return 'An employee with this information already exists.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

@Component({
  selector: 'lpg-feature-employees',
  standalone: true,
  imports: [HeaderPortalDirective, 
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
    DataGridComponent,
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

  protected readonly employees = signal<EmployeeResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly errorMessage = signal<string | null>(null);

  // Modal Visibility Signals
  protected readonly showRegisterModal = signal(false);

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  // Column definitions for employees data grid
  protected readonly columns: DataGridColumn<EmployeeResponse>[] = [
    { field: 'employee_code', header: 'Employee Code', sortable: true, filterable: true },
    { field: 'first_name', header: 'First Name', sortable: true },
    { field: 'last_name', header: 'Last Name', sortable: true },
    { field: 'role', header: 'Role', sortable: true },
    { field: 'status', header: 'Status', sortable: true },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    first_name: ['', [Validators.required]],
    last_name: ['', [Validators.required]],
    phone_number: ['', [Validators.required]],
    email: [''],
    role: ['employee', [Validators.required]],
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
      }
    });

    const unregisterSearch = this.keyboardShortcuts.register({
      key: '/',
      description: 'Focus employee search',
      handler: () => {
        const searchInput = document.getElementById('employee-search-input');
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
      role: 'employee',
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
          this.loadEmployees();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }
}
