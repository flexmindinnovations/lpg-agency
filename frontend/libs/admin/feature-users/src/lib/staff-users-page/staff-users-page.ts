import { HeaderTitlePortalDirective, PageActionsDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { ConfirmationService } from 'primeng/api';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective, ExportButtonComponent } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import {
  AdminStaffUserService,
  AuthService,
  NotifyService,
  type StaffUserResponse,
  errorMessageFor,
} from '@lpg/shared/data-access';
import { ASSIGNABLE_STAFF_ROLES, ROLE_LABELS, roleLabel } from '@lpg/shared/util';
import {
  DataGridComponent,
  type DataGridColumn,
  FormFieldComponent,
  StatusChipCell,
} from '@lpg/shared/ui';
import { ManagePermissionsDialogComponent } from '../manage-permissions-dialog/manage-permissions-dialog';

/** One grid row: the API user plus the derived, displayable fields. */
interface StaffUserRow extends StaffUserResponse {
  readonly name: string;
  readonly status: 'active' | 'inactive';
  readonly isSelf: boolean;
}

const ROLE_OPTIONS = ASSIGNABLE_STAFF_ROLES.map((value) => ({ label: roleLabel(value), value }));

/**
 * Staff list + invite drawer + manage-user drawer —
 * `users:manage`. Customer/Driver accounts are excluded server-side
 * (`ListStaffUsersUseCase`'s own docstring) — this screen is Dashboard
 * staff only.
 *
 * Deactivation always asks first and can be undone with Reactivate (DA-01).
 * Your own row offers neither, and the server also refuses deactivating or
 * demoting the agency's last active admin, so an agency can't lock itself out.
 */
@Component({
  selector: 'lpg-staff-users-page',
  standalone: true,
  imports: [
    ExportButtonComponent,
    PageActionsDirective,
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
    Select,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
    ManagePermissionsDialogComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">Staff Users</h1>
            <p class="page-subtitle">Who can sign in to the dashboard, and what they can do.</p>
          </div>
        </ng-template>
      </div>

      @if (users().length > 0) {
        <ng-template lpgPageActions>
          <button pButton (click)="openInviteDrawer()">
            <i class="pi pi-user-plus"></i><span>Invite User</span>
          </button>
        </ng-template>
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield>
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search users..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
            <span class="data-toolbar__spacer"></span>
            <lpg-export-button (export)="exportCsv()" />
          </div>
        </div>
      }

      @if (!loading() && !loadError() && users().length === 0) {
        <div class="empty-state">
          <i class="pi pi-users empty-state__icon"></i>
          <p class="empty-state__title">No staff users found</p>
          <p class="empty-state__description">Invite the first staff member to get started.</p>
          <button pButton class="mt-4" (click)="openInviteDrawer()">
            <i class="pi pi-user-plus"></i><span>Invite User</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="rows()"
            [columns]="columns"
            [loading]="loading()"
            [error]="loadError()"
            (retry)="reload()"
            [searchQuery]="searchQuery()"
            ariaLabel="Staff users"
          />
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
        <form
          id="inviteUserForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <p class="page-lede">
              Send an invitation email to a new staff member and assign their role.
            </p>

            <lpg-form-field
              label="Email"
              for="invite-email"
              [control]="form.controls.email"
              [messages]="{
                required: 'A valid email address is required.',
                email: 'A valid email address is required.',
              }"
            >
              <input
                pInputText
                id="invite-email"
                type="email"
                formControlName="email"
                placeholder="staff@example.com"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Role"
              for="invite-role"
              [control]="form.controls.role"
              [messages]="{ required: 'Role is required.' }"
            >
              <p-select
                inputId="invite-role"
                formControlName="role"
                [options]="roles"
                optionLabel="label"
                optionValue="value"
                appendTo="body"
                [fluid]="true"
              >
              </p-select>
            </lpg-form-field>
          </div>

          <div class="modal-actions">
            <button
              pButton
              type="button"
              severity="secondary"
              (click)="inviteDrawerVisible.set(false)"
            >
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting()">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
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
        [header]="'Manage ' + (selected()?.name ?? '')"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selected(); as user) {
          <form id="manageUserForm" [formGroup]="manageForm" novalidate class="dialog-form">
            <div class="dialog-form__fields">
              <dl class="user-summary">
                <div>
                  <dt>Email</dt>
                  <dd>{{ user.email || '—' }}</dd>
                </div>
                <div>
                  <dt>Phone</dt>
                  <dd>{{ user.contact_phone || '—' }}</dd>
                </div>
                <div>
                  <dt>Role</dt>
                  <dd>{{ roleName(user.role) }}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{{ user.is_active ? 'Active' : 'Deactivated' }}</dd>
                </div>
              </dl>

              @if (user.isSelf) {
                <p class="self-note" role="note">
                  <i class="pi pi-info-circle" aria-hidden="true"></i>
                  This is your own account. Another admin has to change your role, permissions or
                  status, so you can't lock yourself out by mistake.
                </p>
              } @else {
                <lpg-form-field
                  label="Role"
                  for="manage-role"
                  hint="Changing the role resets permissions to that role's defaults."
                  [control]="manageForm.controls.newRole"
                >
                  <p-select
                    inputId="manage-role"
                    formControlName="newRole"
                    [options]="roles"
                    optionLabel="label"
                    optionValue="value"
                    appendTo="body"
                    [fluid]="true"
                  >
                  </p-select>
                </lpg-form-field>

                <div class="manage-actions">
                  <div class="manage-action">
                    <div class="manage-action__text">
                      <h4 class="manage-action__title">Permissions</h4>
                      <p class="manage-action__description">
                        Fine-tune what this person can do beyond their role.
                      </p>
                    </div>
                    <button
                      pButton
                      type="button"
                      severity="secondary"
                      (click)="openPermissionsDialog()"
                    >
                      Manage
                    </button>
                  </div>

                  @if (user.is_active) {
                    <div class="manage-action manage-action--danger">
                      <div class="manage-action__text">
                        <h4 class="manage-action__title">Deactivate account</h4>
                        <p class="manage-action__description">
                          Signs them out everywhere and blocks sign-in. You can reactivate later.
                        </p>
                      </div>
                      <button
                        pButton
                        type="button"
                        severity="danger"
                        [disabled]="busy()"
                        (click)="confirmDeactivate(user)"
                      >
                        Deactivate
                      </button>
                    </div>
                  } @else {
                    <div class="manage-action">
                      <div class="manage-action__text">
                        <h4 class="manage-action__title">Reactivate account</h4>
                        <p class="manage-action__description">
                          Lets them sign in again with their existing password.
                        </p>
                      </div>
                      <button pButton type="button" [disabled]="busy()" (click)="reactivate(user)">
                        Reactivate
                      </button>
                    </div>
                  }
                </div>
              }
            </div>

            <div class="modal-actions mt-6">
              <button
                pButton
                type="button"
                severity="secondary"
                (click)="manageDrawerVisible.set(false)"
              >
                Close
              </button>
              @if (!user.isSelf) {
                <button
                  pButton
                  type="button"
                  (click)="reassignRole()"
                  [disabled]="busy() || manageForm.controls.newRole.value === user.role"
                >
                  Save role
                </button>
              }
            </div>
          </form>
        }
      </p-drawer>

      <lpg-manage-permissions-dialog
        [(visible)]="managePermissionsVisible"
        [userId]="selected()?.id ?? ''"
        [userEmail]="selected()?.name ?? ''"
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

      /* Action rows in the Manage drawer. Token colours only, so the text
         follows the active theme (light, dark, high contrast). */
      .manage-actions {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-md);
      }

      .manage-action {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        padding: var(--spacing-md);
        border: var(--border-width) solid var(--color-border-strong);
        border-radius: var(--radius-md);
      }

      .manage-action__text {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        min-inline-size: 0;
      }

      .manage-action__title {
        margin: 0;
        font-size: var(--typography-body-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-primary);
      }

      .manage-action__description {
        margin: 0;
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .manage-action--danger {
        border-color: var(--color-status-danger);
        background: color-mix(in srgb, var(--color-status-danger) 8%, transparent);
      }

      .manage-action--danger .manage-action__title {
        color: var(--color-status-danger);
      }

      .user-summary {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--spacing-md);
        margin: 0;
      }

      .user-summary dt {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .user-summary dd {
        margin: 0;
        color: var(--color-text-primary);
        overflow-wrap: anywhere;
      }

      .self-note {
        display: flex;
        gap: var(--spacing-sm);
        margin: 0;
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        background: var(--color-surface-overlay);
        color: var(--color-text-secondary);
      }
    `,
  ],
})
export class StaffUsersPage implements OnInit {
  private readonly grid = viewChild(DataGridComponent);

  /** DA-14: the grid as shown (filtered, sorted, formatted) as a CSV file. */
  protected exportCsv(): void {
    this.grid()?.exportCsv('staff-users');
  }

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly staffUserService = inject(AdminStaffUserService);
  private readonly authService = inject(AuthService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly notify = inject(NotifyService);

  protected readonly users = signal<StaffUserResponse[]>([]);
  protected readonly loading = signal(false);
  /** Set when the list failed to load — the grid shows it with Retry (QA DA-15). */
  protected readonly loadError = signal<string | null>(null);
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly busy = signal(false);
  protected readonly inviteDrawerVisible = signal(false);
  protected readonly manageDrawerVisible = signal(false);
  protected readonly managePermissionsVisible = signal(false);

  private readonly selectedId = signal<string | null>(null);

  protected readonly roles = ROLE_OPTIONS;
  protected readonly roleName = roleLabel;

  protected readonly rows = computed<StaffUserRow[]>(() => {
    const me = this.authService.principal()?.userId;
    return this.users().map((user) => ({
      ...user,
      name: user.display_name || user.email || 'Unnamed user',
      status: user.is_active ? 'active' : 'inactive',
      isSelf: user.id === me,
    }));
  });

  protected readonly selected = computed(
    () => this.rows().find((row) => row.id === this.selectedId()) ?? null,
  );

  protected readonly columns: DataGridColumn<StaffUserRow>[] = [
    {
      field: 'name',
      header: 'Name',
      sortable: true,
      filterable: true,
      valueFormatter: (_value, row) => (row.isSelf ? `${row.name} (you)` : row.name),
      onLinkClick: (row) => this.openManageDrawer(row),
    },
    { field: 'email', header: 'Email', sortable: true, filterable: true },
    {
      field: 'role',
      header: 'Role',
      sortable: true,
      filterable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { labelMap: ROLE_LABELS, severityMap: { agency_admin: 'info' } },
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        labelMap: { active: 'Active', inactive: 'Deactivated' },
        severityMap: { active: 'success', inactive: 'secondary' },
      },
    },
    {
      field: 'id',
      header: 'Action',
      // Never one click: Deactivate asks first, Reactivate undoes it, and
      // your own row offers neither (DA-01).
      valueFormatter: (_value, row) =>
        row.isSelf ? '' : row.is_active ? 'Deactivate…' : 'Reactivate',
      onLinkClick: (row) => {
        if (row.isSelf) return;
        if (row.is_active) this.confirmDeactivate(row);
        else this.reactivate(row);
      },
    },
  ];

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
    role: ['', [Validators.required]],
  });

  protected readonly manageForm = this.formBuilder.group({
    newRole: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.staffUserService.listStaffUsers().subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(errorMessageFor(error));
        this.loading.set(false);
      },
    });
  }

  protected openInviteDrawer(): void {
    this.form.reset();
    this.inviteDrawerVisible.set(true);
  }

  protected openManageDrawer(user: StaffUserRow): void {
    this.selectedId.set(user.id);
    this.manageForm.reset({ newRole: user.role });
    this.manageDrawerVisible.set(true);
  }

  protected openPermissionsDialog(): void {
    this.managePermissionsVisible.set(true);
  }

  protected confirmDeactivate(user: StaffUserRow): void {
    this.confirmationService.confirm({
      header: 'Deactivate this account?',
      message:
        `${user.name} will be signed out everywhere and won't be able to sign in. ` +
        'You can reactivate the account later.',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Deactivate',
      rejectLabel: 'Cancel',
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary' },
      defaultFocus: 'reject',
      accept: () => this.deactivate(user),
    });
  }

  private deactivate(user: StaffUserRow): void {
    this.busy.set(true);
    this.staffUserService.deactivateStaffUser(user.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.notify.success(`${user.name} has been deactivated.`);
        this.reload();
      },
      error: () => this.busy.set(false),
    });
  }

  protected reactivate(user: StaffUserRow): void {
    this.busy.set(true);
    this.staffUserService.reactivateStaffUser(user.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.notify.success(`${user.name} can sign in again.`);
        this.reload();
      },
      error: () => this.busy.set(false),
    });
  }

  protected reassignRole(): void {
    const user = this.selected();
    const { newRole } = this.manageForm.getRawValue();
    if (!user || !newRole || newRole === user.role) return;
    this.busy.set(true);
    this.staffUserService.reassignRole(user.id, newRole).subscribe({
      next: () => {
        this.busy.set(false);
        this.notify.success(`${user.name} is now ${roleLabel(newRole)}.`);
        this.manageDrawerVisible.set(false);
        this.reload();
      },
      error: () => this.busy.set(false),
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
        this.notify.success(`${email} has been invited.`);
        this.inviteDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }
}
