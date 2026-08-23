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
import { forkJoin, type Observable } from 'rxjs';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  StatusChipCell,
  type ChipSeverity,
  toSentenceCase,
} from '@lpg/shared/ui';
import { KeyboardShortcutsService } from '@lpg/shared/util';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { MessageService } from 'primeng/api';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import {
  AdminBranchService,
  DeliveryService,
  type AppError,
  type BranchResponse,
  type VehicleResponse,
} from '@lpg/shared/data-access';

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
    DataGridComponent,
    HasPermissionDirective,
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
  private readonly messageService = inject(MessageService);

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
  });

  protected get registerModalVisible(): boolean {
    return this.showRegisterModal();
  }
  protected set registerModalVisible(value: boolean) {
    this.showRegisterModal.set(value);
  }

  ngOnInit(): void {
    this.loadBranches();
    this.loadVehicles();


    const unregisterNew = this.keyboardShortcuts.register({
      key: 'n',
      alt: true,
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

  protected openDetails(vehicle: VehicleResponse): void {
    this.selectedVehicle.set(vehicle);
    this.editMode.set(false);
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
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
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Vehicle updated.' });
        this.loadVehicles();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
      },
    });
  }
}
