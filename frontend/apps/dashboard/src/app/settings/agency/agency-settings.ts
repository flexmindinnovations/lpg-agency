import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { DetailItemComponent, DetailListComponent, SectionCardComponent } from '@lpg/shared/ui';
import { AdminTenantService } from '@lpg/shared/data-access';

/**
 * Read-only agency identity. The agency code is the tenant slug that drivers
 * and customers type to sign in to the mobile apps, so it is surfaced here
 * with that explanation. Nothing on this page is editable today — the tenant
 * name has no self-service edit outside Tenant Config.
 */
@Component({
  selector: 'lpg-agency-settings',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    SectionCardComponent,
    DetailListComponent,
    DetailItemComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
        <h1 class="page-title">Agency</h1>
        <p class="page-subtitle">Your agency’s identity and subscription details.</p>
      </div>
    </ng-template>

    @if (tenant(); as agency) {
      <lpg-section-card class="detail-view">
        <lpg-detail-list>
          <lpg-detail-item label="Agency name">{{ agency.name }}</lpg-detail-item>
          <lpg-detail-item label="Agency code">
            <span class="agency-code">{{ agency.slug }}</span>
            <span class="agency-code-hint">
              Drivers and customers enter this code when signing in to the mobile apps.
            </span>
          </lpg-detail-item>
          <lpg-detail-item label="Status">
            <span class="capitalize">{{ agency.status }}</span>
          </lpg-detail-item>
          <lpg-detail-item label="Plan">
            <span class="capitalize">{{ agency.subscription_plan }}</span>
          </lpg-detail-item>
          <lpg-detail-item label="Primary contact">{{
            agency.primary_contact_email
          }}</lpg-detail-item>
          <lpg-detail-item label="Country">{{ agency.country }}</lpg-detail-item>
        </lpg-detail-list>
      </lpg-section-card>
    } @else if (tenant() === null) {
      <p class="state-message" role="alert">
        Couldn’t load your agency details. Refresh the page to try again.
      </p>
    } @else {
      <p class="state-message" role="status">Loading agency details…</p>
    }
  `,
  styles: [
    `
      .detail-view {
        max-inline-size: 480px;
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

      .state-message {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
    `,
  ],
})
export class AgencySettings {
  private readonly tenantService = inject(AdminTenantService);

  /** `undefined` while loading, `null` if the request failed, else the tenant. */
  protected readonly tenant = toSignal(
    this.tenantService.getTenant().pipe(catchError(() => of(null))),
  );
}
