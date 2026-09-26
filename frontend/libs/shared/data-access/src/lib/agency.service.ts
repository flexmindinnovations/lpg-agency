import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { addAgencyAdminApiV1PlatformAgenciesTenantIdAdminsPost } from './generated/fn/platform-console/add-agency-admin-api-v-1-platform-agencies-tenant-id-admins-post';
import { issueAgencyAdminSetupLinkApiV1PlatformAgenciesTenantIdUsersUserIdSetupLinkPost } from './generated/fn/platform-console/issue-agency-admin-setup-link-api-v-1-platform-agencies-tenant-id-users-user-id-setup-link-post';
import { listAgencyUsersApiV1PlatformAgenciesTenantIdUsersGet } from './generated/fn/platform-console/list-agency-users-api-v-1-platform-agencies-tenant-id-users-get';
import { createAgencyApiV1PlatformAgenciesPost } from './generated/fn/platform-console/create-agency-api-v-1-platform-agencies-post';
import { closeAgencyApiV1PlatformAgenciesTenantIdClosePatch } from './generated/fn/platform-console/close-agency-api-v-1-platform-agencies-tenant-id-close-patch';
import { listAgenciesApiV1PlatformAgenciesGet } from './generated/fn/platform-console/list-agencies-api-v-1-platform-agencies-get';
import { reactivateAgencyApiV1PlatformAgenciesTenantIdReactivatePatch } from './generated/fn/platform-console/reactivate-agency-api-v-1-platform-agencies-tenant-id-reactivate-patch';
import { suspendAgencyApiV1PlatformAgenciesTenantIdSuspendPatch } from './generated/fn/platform-console/suspend-agency-api-v-1-platform-agencies-tenant-id-suspend-patch';
import type { AgencyUserSetupResponse } from './generated/models/agency-user-setup-response';
import type { StaffUserResponse } from './generated/models/staff-user-response';
import type { CreateAgencyRequest } from './generated/models/create-agency-request';
import type { CreateAgencyResponse } from './generated/models/create-agency-response';
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

  /** Creates an agency and its first admin. The response carries the
   * one-time password-setup link — it is never retrievable again. */
  create(request: CreateAgencyRequest): Observable<CreateAgencyResponse> {
    return createAgencyApiV1PlatformAgenciesPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((response) => response.body));
  }

  /** An agency's staff users (metadata only) - Super Admin recovery tooling. */
  listUsers(tenantId: string): Observable<StaffUserResponse[]> {
    return listAgencyUsersApiV1PlatformAgenciesTenantIdUsersGet(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
    }).pipe(map((response) => response.body));
  }

  /** Adds another `agency_admin`; the response carries their one-time setup link. */
  addAdmin(tenantId: string, email: string): Observable<AgencyUserSetupResponse> {
    return addAgencyAdminApiV1PlatformAgenciesTenantIdAdminsPost(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
      body: { email },
    }).pipe(map((response) => response.body));
  }

  /** Issues a fresh one-time setup link for an existing `agency_admin`; any
   * older unused link for that user stops working. */
  issueSetupLink(tenantId: string, userId: string): Observable<AgencyUserSetupResponse> {
    return issueAgencyAdminSetupLinkApiV1PlatformAgenciesTenantIdUsersUserIdSetupLinkPost(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, user_id: userId },
    ).pipe(map((response) => response.body));
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
