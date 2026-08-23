import { ChangeDetectionStrategy, Component, inject, input, output, signal, effect, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { MessageService } from 'primeng/api';
import { CheckboxModule } from 'primeng/checkbox';
import { FieldsetModule } from 'primeng/fieldset';
import { TooltipModule } from 'primeng/tooltip';
import { AdminStaffUserService, type AppError } from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong. Please try again.';
  }
}

const PERMISSION_DESCRIPTIONS: Record<string, string> = {
  'audit:read': 'View system audit logs tracking user activity.',
  'complaints.manage': 'Full access to manage customer complaints.',
  'complaints:create': 'Create new customer complaints.',
  'complaints:read': 'View existing customer complaints.',
  'complaints:resolve': 'Mark complaints as resolved.',
  'credit_notes:approve': 'Approve requested credit notes.',
  'credit_notes:request': 'Request credit notes for customers.',
  'customers:create': 'Add new customers to the system.',
  'customers:read': 'View customer profiles and history.',
  'customers:update': 'Modify existing customer profiles.',
  'drivers:manage': 'Manage driver accounts and assignments.',
  'drivers:read': 'View driver profiles and status.',
  'feature_flags:manage_platform': 'Manage platform-wide feature flags (Super Admin).',
  'feature_flags:manage_tenant': 'Manage tenant-specific feature flags.',
  'inventory:adjust': 'Make manual adjustments to inventory levels.',
  'inventory:load': 'Record incoming inventory loads.',
  'inventory:read': 'View current inventory levels.',
  'invoices:read': 'View customer invoices and payment status.',
  'kyc:manage': 'Review, approve, or reject KYC documents.',
  'kyc:read': 'View customer KYC status and uploaded documents.',
  'ledger:read': 'View cylinder ledger and transaction history.',
  'ledger:write': 'Record entries in the cylinder ledger.',
  'license:manage_platform': 'Issue, revoke, and manage every tenant’s license (Super Admin).',
  'license:manage_tenant': 'Activate this tenant’s license and manage its linked devices.',
  'orders:manage': 'Create, edit, and cancel customer orders.',
  'orders:read': 'View order details and status.',
  'pricing:manage': 'Update price lists and discounts.',
  'pricing:read': 'View current pricing configurations.',
  'reports:read': 'Access and view system reports.',
  'tenant:configure': 'Modify agency/tenant settings.',
  'users:manage': 'Manage staff user accounts and roles.',
  'users:read': 'View staff user list and details.',
  'vehicles:manage': 'Manage fleet vehicles and assignments.',
  'vehicles:read': 'View the list of fleet vehicles.',
};

@Component({
  selector: 'lpg-manage-permissions-dialog',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, DialogModule, ButtonModule, CheckboxModule, FieldsetModule, TooltipModule],
  template: `
    <p-dialog
      [visible]="visible()"
      (visibleChange)="visibleChange.emit($event)"
      [modal]="true"
      [closeOnEscape]="true"
      [header]="'Manage Permissions for ' + userEmail()"
      [style]="{ width: '40rem', maxWidth: '100%' }"
      (onHide)="onHide()"
    >
      <div class="dialog-content">
        <p class="page-lede mb-4">Select the specific permissions to assign to this user. Note that role-based permissions are applied implicitly and cannot be removed here.</p>
        
        @if (loading()) {
          <div class="flex justify-center p-4">
            <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
          </div>
        } @else {
          <form [formGroup]="form" (ngSubmit)="submit()">
            <div class="permissions-container">
              @for (group of groupedPermissions(); track group.module) {
                <p-fieldset [legend]="group.module.replace('_', ' ') | titlecase" [toggleable]="true" styleClass="mb-4">
                  <div class="permissions-grid">
                    @for (perm of group.permissions; track perm) {
                      <div class="permission-item gap-2">
                        <p-checkbox
                          [binary]="true"
                          [formControlName]="perm"
                          [inputId]="perm"
                        ></p-checkbox>
                        <label [for]="perm" class="flex items-center gap-1 cursor-pointer">
                          {{ perm.substring(group.module.length + 1) | titlecase }}
                          @if (getPermissionDescription(perm); as desc) {
                            <i class="pi pi-info-circle text-gray-400" [pTooltip]="desc" tooltipPosition="top"></i>
                          }
                        </label>
                      </div>
                    }
                  </div>
                </p-fieldset>
              }
            </div>

            <div class="modal-actions mt-6">
              <button pButton type="button" severity="secondary" (click)="visibleChange.emit(false)">Cancel</button>
              <button pButton type="submit" [disabled]="submitting()" [loading]="submitting()">Save Permissions</button>
            </div>
          </form>
        }
      </div>
    </p-dialog>
  `,
  styles: [
    `
      .permissions-container {
        max-height: 50vh;
        overflow-y: auto;
        padding-right: 0.5rem;
      }
      .permissions-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 1rem;
      }
      .permission-item {
        display: flex;
        align-items: center;
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ManagePermissionsDialogComponent {
  private readonly staffUserService = inject(AdminStaffUserService);
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(FormBuilder);

  readonly visible = input.required<boolean>();
  readonly userId = input.required<string>();
  readonly userEmail = input.required<string>();

  readonly visibleChange = output<boolean>();
  readonly permissionsUpdated = output<void>();

  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly availablePermissions = signal<string[]>([]);
  
  protected readonly groupedPermissions = computed(() => {
    const perms = this.availablePermissions();
    const groups: { module: string; permissions: string[] }[] = [];
    const map = new Map<string, string[]>();
    for (const p of perms) {
      const parts = p.split(/[:.]/);
      const moduleName = parts[0];
      if (!map.has(moduleName)) {
        map.set(moduleName, []);
      }
      map.get(moduleName)!.push(p);
    }
    map.forEach((permissions, module) => {
      groups.push({ module, permissions });
    });
    return groups.sort((a, b) => a.module.localeCompare(b.module));
  });

  protected form = this.fb.group({});

  getPermissionDescription(perm: string): string | null {
    return PERMISSION_DESCRIPTIONS[perm] || null;
  }

  constructor() {
    effect(() => {
      if (this.visible() && this.userId()) {
        this.loadData();
      }
    }, { allowSignalWrites: true });
  }

  private loadData(): void {
    this.loading.set(true);
    
    // Run both requests concurrently
    this.staffUserService.listPermissions().subscribe({
      next: (allPerms) => {
        this.availablePermissions.set(allPerms);
        
        // Create form controls for each permission
        const group: Record<string, any> = {};
        allPerms.forEach(perm => {
          group[perm] = [false];
        });
        this.form = this.fb.group(group);

        // Fetch user's assigned permissions
        this.staffUserService.getUserPermissions(this.userId()).subscribe({
          next: (userPerms) => {
            const patchValue: Record<string, boolean> = {};
            userPerms.forEach(perm => {
              if (this.form.contains(perm)) {
                patchValue[perm] = true;
              }
            });
            this.form.patchValue(patchValue);
            this.loading.set(false);
          },
          error: (err) => {
            this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
            this.loading.set(false);
          }
        });
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
        this.loading.set(false);
      }
    });
  }

  protected submit(): void {
    this.submitting.set(true);
    
    // Extract selected permissions
    const formValue = this.form.getRawValue();
    const selectedPermissions = Object.keys(formValue).filter(key => (formValue as Record<string, any>)[key] === true);

    this.staffUserService.updateUserPermissions(this.userId(), selectedPermissions).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Permissions updated successfully.' });
        this.submitting.set(false);
        this.permissionsUpdated.emit();
        this.visibleChange.emit(false);
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
        this.submitting.set(false);
      }
    });
  }

  protected onHide(): void {
    this.form.reset();
  }
}
