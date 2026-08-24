import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { closeAgencyApiV1PlatformAgenciesTenantIdClosePatch } from './generated/fn/platform-console/close-agency-api-v-1-platform-agencies-tenant-id-close-patch';
import { listAgenciesApiV1PlatformAgenciesGet } from './generated/fn/platform-console/list-agencies-api-v-1-platform-agencies-get';
import { reactivateAgencyApiV1PlatformAgenciesTenantIdReactivatePatch } from './generated/fn/platform-console/reactivate-agency-api-v-1-platform-agencies-tenant-id-reactivate-patch';
import { suspendAgencyApiV1PlatformAgenciesTenantIdSuspendPatch } from './generated/fn/platform-console/suspend-agency-api-v-1-platform-agencies-tenant-id-suspend-patch';
import type { TenantResponse } from './generated/models/tenant-response';

/**
 * Thin wrapper over the generated `/platform/agencies*` client functions —
 * `super_admin` only, `tenant:manage_platform`, live-checked server-side.
 * Metadata only (name, slug, status, plan) — never tenant business data,
 * by design (Platform Console plan, "Out of scope").
 */
@Injectable({ providedIn: 'root' })
export class AgencyService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listAgencies(): Observable<TenantResponse[]> {
    return listAgenciesApiV1PlatformAgenciesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  suspend(tenantId: string): Observable<void> {
    return suspendAgencyApiV1PlatformAgenciesTenantIdSuspendPatch(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
    }).pipe(map(() => undefined));
  }

  reactivate(tenantId: string): Observable<void> {
    return reactivateAgencyApiV1PlatformAgenciesTenantIdReactivatePatch(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId },
    ).pipe(map(() => undefined));
  }

  close(tenantId: string): Observable<void> {
    return closeAgencyApiV1PlatformAgenciesTenantIdClosePatch(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
    }).pipe(map(() => undefined));
  }
}
