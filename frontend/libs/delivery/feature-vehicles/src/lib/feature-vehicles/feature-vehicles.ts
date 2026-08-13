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
  DeliveryService,
  AdminBranchService,
  type AppError,
  type BranchResponse,
  type VehicleResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_REGISTRATION_NUMBER':
      return 'A vehicle with this registration number already exists.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

@Component({
  selector: 'lpg-feature-vehicles',
  standalone: true,
  imports: [
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
  templateUrl: './feature-vehicles.html',
  styleUrl: './feature-vehicles.css',
})
export class FeatureVehicles implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly deliveryService = inject(DeliveryService);
  private readonly branchService = inject(AdminBranchService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly vehicles = signal<VehicleResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly selectedVehicle = signal<VehicleResponse | null>(null);
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

  // Column definitions for vehicles data grid
  protected readonly columns: DataGridColumn<VehicleResponse>[] = [
    {
      field: 'registration_number',
      header: 'Reg No.',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openStatusModal(row),
    },
    { field: 'make', header: 'Make', sortable: true },
    { field: 'model', header: 'Model', sortable: true },
    { field: 'ownership_type', header: 'Ownership', sortable: true },
    { field: 'capacity_units', header: 'Capacity (Cylinders)', sortable: true },
    { field: 'status', header: 'Status', sortable: true },
  ];

  // Forms
  protected readonly registerForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    registration_number: ['', [Validators.required]],
    make: ['', [Validators.required]],
    model: ['', [Validators.required]],
    ownership_type: ['owned', [Validators.required]],
    capacity_units: [20, [Validators.required, Validators.min(1)]],
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
    this.loadVehicles();

    const unregisterNew = this.keyboardShortcuts.register({
      key: 'n',
      ctrl: true,
      description: 'Register new vehicle',
      handler: () => {
        if (!this.showRegisterModal()) {
          this.openRegisterModal();
        }
      }
    });

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
    });
    this.showRegisterModal.set(true);
  }

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) return;

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

  protected openStatusModal(vehicle: VehicleResponse): void {
    this.selectedVehicle.set(vehicle);
    this.statusForm.patchValue({ status: vehicle.status });
    this.showUpdateStatusModal.set(true);
  }

  protected onSubmitStatus(): void {
    const vehicle = this.selectedVehicle();
    if (!vehicle || this.statusForm.invalid) return;

    const newStatus = this.statusForm.getRawValue().status;
    this.loading.set(true);
    this.deliveryService.updateVehicleStatus(vehicle.id, newStatus).subscribe({
      next: () => {
        this.showUpdateStatusModal.set(false);
        this.loadVehicles();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }
}
