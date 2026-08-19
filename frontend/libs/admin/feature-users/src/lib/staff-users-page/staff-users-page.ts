import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
import {
  AdminStaffUserService,
  type AppError,
  type StaffUserResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, StatusChipCell } from '@lpg/shared/ui';
import { ManagePermissionsDialogComponent } from '../manage-permissions-dialog/manage-permissions-dialog';

const STAFF_ROLES = [
  { label: 'Super Admin (super_admin)', value: 'super_admin' },
  { label: 'Agency Admin (agency_admin)', value: 'agency_admin' },
  { label: 'Manager (manager)', value: 'manager' },
  { label: 'Warehouse Staff (warehouse_staff)', value: 'warehouse_staff' },
  { label: 'Dispatcher (dispatcher)', value: 'dispatcher' },
  { label: 'Accountant (accountant)', value: 'accountant' },
];

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong. Please try again.';
  }
}

/**
 * Staff list + invite drawer + manage-user drawer —
 * `users:manage`. Customer/Driver accounts are excluded server-side
 * (`ListStaffUsersUseCase`'s own docstring) — this screen is Dashboard
 * staff only.
 */
@Component({
  selector: 'lpg-staff-users-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, Select, Drawer, IconField, InputIcon, ManagePermissionsDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">Staff Users</h1>
            <p class="page-subtitle">Manage user accounts and role assignments.</p>
          </div>
        </ng-template>
        <ng-template lpgHeaderPortal>
          <div class="page-header__actions">
            <button pButton (click)="openInviteDrawer()"><i pButtonIcon class="pi pi-user-plus"></i><span pButtonLabel>Invite User</span></button>
          </div>
        </ng-template>
      </div>

      @if (users().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon styleClass="pi pi-search" />
              <input pInputText type="text" placeholder="Search users..." class="w-full" />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
          </div>
        </div>
      }

      @if (!loading() && users().length === 0) {
        <div class="empty-state">
          <i class="pi pi-users empty-state__icon"></i>
          <p class="empty-state__title">No staff users found</p>
          <p class="empty-state__description">Invite the first staff member to get started.</p>
          <button pButton class="mt-4" (click)="openInviteDrawer()"><i pButtonIcon class="pi pi-user-plus"></i><span pButtonLabel>Invite User</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="users()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Staff users"
            />
          </div>
        </section>
      }

      <!-- Invite User Drawer -->
      <p-drawer
        [(visible)]="inviteDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Invite a staff user"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="inviteUserForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <p class="page-lede">Send an invitation email to a new staff member and assign their role.</p>

          <div class="form-group">
            <label for="invite-email">Email</label>
            <input pInputText id="invite-email" type="email" formControlName="email" placeholder="staff@example.com" />
            @if (form.controls.email.touched && form.controls.email.invalid) {
              <small class="field-error">A valid email address is required.</small>
            }
          </div>

          <div class="form-group">
            <label for="invite-role">Role</label>
            <p-select
              id="invite-role"
              formControlName="role"
              [options]="roles"
              optionLabel="label"
              optionValue="value"
              placeholder="Select a role"
              styleClass="w-full"
              appendTo="body">
            </p-select>
            @if (form.controls.role.touched && form.controls.role.invalid) {
              <small class="field-error">Role is required.</small>
            }
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="inviteDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Send invite
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Manage User Drawer -->
      <p-drawer
        [(visible)]="manageDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        [header]="'Manage ' + selectedUserEmail()"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="manageUserForm" [formGroup]="manageForm" novalidate class="dialog-form">
          <p class="page-lede">Reassign the role, manage specific permissions, or deactivate the account.</p>

          <div class="form-group">
            <label for="manage-role">New role (for reassignment)</label>
            <p-select
              id="manage-role"
              formControlName="newRole"
              [options]="roles"
              optionLabel="label"
              optionValue="value"
              placeholder="- select to reassign -"
              styleClass="w-full"
              appendTo="body">
            </p-select>
          </div>

          <div class="flex flex-col gap-4 mt-6">
            <div class="flex items-center justify-between border border-gray-200 rounded p-4">
               <div>
                 <h4 class="font-medium text-gray-900 m-0">Permissions</h4>
                 <p class="text-sm text-gray-500 m-0">Assign fine-grained permissions.</p>
               </div>
               <button pButton type="button" severity="secondary" (click)="openPermissionsDialog()">Manage</button>
            </div>
            
            <div class="flex items-center justify-between border border-red-200 rounded p-4 bg-red-50">
               <div>
                 <h4 class="font-medium text-red-900 m-0">Danger Zone</h4>
                 <p class="text-sm text-red-700 m-0">Deactivate this account.</p>
               </div>
               <button pButton type="button" severity="danger" (click)="deactivate()">Deactivate</button>
            </div>
          </div>

          <div class="modal-actions mt-6">
            <button pButton type="button" severity="secondary" (click)="manageDrawerVisible.set(false)">Cancel</button>
            <button pButton type="button" (click)="reassignRole()" [disabled]="!manageForm.controls.newRole.value">
              Reassign role
            </button>
          </div>
        </form>
      </p-drawer>

      <lpg-manage-permissions-dialog 
        [(visible)]="managePermissionsVisible"
        [userId]="selectedUserId()"
        [userEmail]="selectedUserEmail()"
      />
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .admin-page {
        display: flex;
        flex-direction: column;
        block-size: 100%;
      }

      .grid-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-block-size: 0;
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }
    `,
  ],
})
export class StaffUsersPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly staffUserService = inject(AdminStaffUserService);
  private readonly messageService = inject(MessageService);

  protected readonly users = signal<StaffUserResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly inviteDrawerVisible = signal(false);
  protected readonly manageDrawerVisible = signal(false);
  protected readonly managePermissionsVisible = signal(false);
  
  protected readonly selectedUserId = signal('');
  protected readonly selectedUserEmail = signal('');

  protected readonly roles = [...STAFF_ROLES];

  protected readonly columns: DataGridColumn<StaffUserResponse>[] = [
    { 
      field: 'email', 
      header: 'Email', 
      sortable: true, 
      filterable: true, 
      onLinkClick: (row) => this.openManageDrawer(row) 
    },
    { field: 'role', header: 'Role', sortable: true, filterable: true, cellRenderer: StatusChipCell },
    { field: 'is_active', header: 'Active', sortable: true },
  ];

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
    role: ['', [Validators.required]],
  });

  protected readonly manageForm = this.formBuilder.group({
    userId: ['', [Validators.required]],
    newRole: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.staffUserService.listStaffUsers().subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openInviteDrawer(): void {
    this.form.reset();
    this.inviteDrawerVisible.set(true);
  }

  protected openManageDrawer(user: StaffUserResponse): void {
    this.manageForm.reset();
    this.selectedUserId.set(user.id);
    this.selectedUserEmail.set(user.email ?? '');
    this.manageForm.patchValue({ userId: user.id });
    this.manageDrawerVisible.set(true);
  }

  protected openPermissionsDialog(): void {
    this.managePermissionsVisible.set(true);
  }

  protected deactivate(): void {
    const { userId } = this.manageForm.getRawValue();
    if (!userId) {
      this.manageForm.markAllAsTouched();
      return;
    }
    this.staffUserService.deactivateStaffUser(userId).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'User deactivated.' });
        this.manageDrawerVisible.set(false);
        this.reload();
      },
      error: (error: unknown) =>
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) }),
    });
  }

  protected reassignRole(): void {
    const { userId, newRole } = this.manageForm.getRawValue();
    if (!userId || !newRole) {
      this.manageForm.markAllAsTouched();
      return;
    }
    this.staffUserService.reassignRole(userId, newRole).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Role reassigned.' });
        this.manageDrawerVisible.set(false);
        this.reload();
      },
      error: (error: unknown) =>
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) }),
    });
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { email, role } = this.form.getRawValue();

    this.staffUserService.inviteStaffUser(email, role).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `Invite sent to ${email}.` });
        this.inviteDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
