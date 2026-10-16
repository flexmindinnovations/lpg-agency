import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { DetailItemComponent, DetailListComponent, SectionCardComponent } from '@lpg/shared/ui';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of } from 'rxjs';
import { AdminTenantService, AuthService } from '@lpg/shared/data-access';

/**
 * Read-only account summary — reachable from the profile menu's "My
 * Profile" item. No edit form yet: the identity domain has no writable
 * self-service fields today (role/tenant are admin-managed, and this app
 * has no `full_name` column to edit — see `ProfileMenuComponent`'s
 * `displayNameFromEmail` doc comment). A real destination that's honest
 * about what it can do, rather than a stub.
 */
@Component({
  selector: 'lpg-profile',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    SectionCardComponent,
    DetailListComponent,
    DetailItemComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="profile-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">My Profile</h1>
            <p class="page-subtitle">
              Your account information. Contact an administrator to update your role or email.
            </p>
          </div>
        </ng-template>
      </div>

      <lpg-section-card class="detail-view">
        <lpg-detail-list>
          <lpg-detail-item label="Email address">{{ email() || 'Not set' }}</lpg-detail-item>
          <lpg-detail-item label="Role">
            <span class="capitalize">{{ role() || 'Not assigned' }}</span>
          </lpg-detail-item>
          @if (agencyCode(); as code) {
            <lpg-detail-item label="Agency code">
              <span class="agency-code">{{ code }}</span>
              <span class="agency-code-hint">
                Drivers and customers enter this code when signing in to the mobile apps.
              </span>
            </lpg-detail-item>
          }
        </lpg-detail-list>
      </lpg-section-card>
    </div>
  `,
  styles: [
    `
      .detail-view {
        max-inline-size: 480px;
        margin-block-start: var(--spacing-lg);
      }

      .agency-code {
        font-family: var(--typography-font-family-mono);
        font-weight: var(--typography-label-font-weight);
        letter-spacing: 0.04em;
      }

      .agency-code-hint {
        display: block;
        margin-block-start: var(--spacing-xs);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }
    `,
  ],
})
export class Profile {
  private readonly authService = inject(AuthService);
  private readonly tenantService = inject(AdminTenantService);

  protected readonly email = computed(() => this.authService.principal()?.email ?? null);
  protected readonly role = computed(() => this.authService.principal()?.role ?? '');

  // Roles without `tenant:read` (and the tenant-less Super Admin) get a 403/404 —
  // the row simply stays hidden rather than showing an error on a read-only page.
  protected readonly agencyCode = toSignal(
    this.tenantService.getTenant().pipe(
      map((tenant) => tenant.slug),
      catchError(() => of(null)),
    ),
    { initialValue: null },
  );
}
