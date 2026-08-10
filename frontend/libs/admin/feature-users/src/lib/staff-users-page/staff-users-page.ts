import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AdminStaffUserService,
  type AppError,
  type StaffUserResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

const STAFF_ROLES = [
  'super_admin',
  'agency_admin',
  'manager',
  'warehouse_staff',
  'dispatcher',
  'accountant',
] as const;

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
 * Staff list + invite form + deactivate/reassign-role actions —
 * `users:manage`. Customer/Driver accounts are excluded server-side
 * (`ListStaffUsersUseCase`'s own docstring) — this screen is Dashboard
 * staff only.
 */
@Component({
  selector: 'lpg-staff-users-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Staff Users</h1>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="users()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Staff users"
        />
      </div>

      <form class="admin-page__form" [formGroup]="manageForm" novalidate>
        <h2>Manage a user</h2>
        <p class="admin-page__hint">Copy a user's id from the grid above.</p>
        <div class="admin-page__field">
          <label for="manage-user-id">User id</label>
          <input pInputText id="manage-user-id" type="text" formControlName="userId" />
        </div>
        <div class="admin-page__field">
          <label for="manage-role">New role (for reassignment)</label>
          <select id="manage-role" formControlName="newRole">
            <option value="">— select to reassign —</option>
            @for (role of roles; track role) {
              <option [value]="role">{{ role }}</option>
            }
          </select>
        </div>
        <div class="admin-page__actions">
          <button pButton type="button" severity="secondary" (click)="reassignRole()">
            Reassign role
          </button>
          <button pButton type="button" severity="danger" (click)="deactivate()">Deactivate</button>
        </div>
      </form>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Invite a staff user</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="invite-email">Email</label>
          <input pInputText id="invite-email" type="email" formControlName="email" />
        </div>
        <div class="admin-page__field">
          <label for="invite-role">Role</label>
          <select id="invite-role" formControlName="role">
            <option value="" disabled>Select a role</option>
            @for (role of roles; track role) {
              <option [value]="role">{{ role }}</option>
            }
          </select>
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Inviting…' : 'Send invite' }}
        </button>
      </form>
    </div>
  `,
  styles: [
    `
      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
      }

      .admin-page__grid {
        block-size: 400px;
      }

      .admin-page__form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        max-inline-size: 24rem;
      }

      .admin-page__field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .admin-page__hint {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      .admin-page__actions {
        display: flex;
        gap: var(--spacing-sm);
      }
    `,
  ],
})
export class StaffUsersPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly staffUserService = inject(AdminStaffUserService);

  protected readonly users = signal<StaffUserResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly roles = STAFF_ROLES;

  protected readonly columns: DataGridColumn<StaffUserResponse>[] = [
    { field: 'email', header: 'Email', sortable: true, filterable: true },
    { field: 'role', header: 'Role', sortable: true, filterable: true },
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

  protected deactivate(): void {
    const { userId } = this.manageForm.getRawValue();
    if (!userId) {
      this.manageForm.markAllAsTouched();
      return;
    }
    this.staffUserService.deactivateStaffUser(userId).subscribe(() => this.reload());
  }

  protected reassignRole(): void {
    const { userId, newRole } = this.manageForm.getRawValue();
    if (!userId || !newRole) {
      this.manageForm.markAllAsTouched();
      return;
    }
    this.staffUserService.reassignRole(userId, newRole).subscribe(() => this.reload());
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
    this.errorMessage.set(null);
    const { email, role } = this.form.getRawValue();

    this.staffUserService.inviteStaffUser(email, role).subscribe({
      next: () => {
        this.submitting.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
