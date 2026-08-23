import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { activateLicenseApiV1AdminLicenseActivatePost } from './generated/fn/administration/activate-license-api-v-1-admin-license-activate-post';
import { getLicenseStatusApiV1AdminLicenseStatusGet } from './generated/fn/administration/get-license-status-api-v-1-admin-license-status-get';
import { issueLicenseApiV1AdminLicensePost } from './generated/fn/administration/issue-license-api-v-1-admin-license-post';
import { listLicensesApiV1AdminLicenseGet } from './generated/fn/administration/list-licenses-api-v-1-admin-license-get';
import { listLinkedDevicesApiV1AdminLicenseDevicesGet } from './generated/fn/administration/list-linked-devices-api-v-1-admin-license-devices-get';
import { revokeLicenseApiV1AdminLicenseTenantIdRevokePatch } from './generated/fn/administration/revoke-license-api-v-1-admin-license-tenant-id-revoke-patch';
import { revokeLinkedDeviceApiV1AdminLicenseDevicesDeviceIdRevokePatch } from './generated/fn/administration/revoke-linked-device-api-v-1-admin-license-devices-device-id-revoke-patch';
import { setLicenseDeviceCapApiV1AdminLicenseTenantIdDeviceCapsAppTypePatch } from './generated/fn/administration/set-license-device-cap-api-v-1-admin-license-tenant-id-device-caps-app-type-patch';
import { setLicenseFeatureOverrideApiV1AdminLicenseTenantIdFeatureOverridesKeyPut } from './generated/fn/administration/set-license-feature-override-api-v-1-admin-license-tenant-id-feature-overrides-key-put';
import { setLicensePlanTierApiV1AdminLicenseTenantIdPlanTierPatch } from './generated/fn/administration/set-license-plan-tier-api-v-1-admin-license-tenant-id-plan-tier-patch';
import type { IssuedLicenseResponse } from './generated/models/issued-license-response';
import type { LicenseResponse } from './generated/models/license-response';
import type { LicenseStatusResponse } from './generated/models/license-status-response';
import type { LinkedDeviceResponse } from './generated/models/linked-device-response';

/**
 * Thin wrapper over the generated `/admin/license*` client functions.
 *
 * Platform-management methods (`issueLicense`, `revokeLicense`,
 * `setPlanTier`, `setDeviceCap`, `setFeatureOverride`, `listLicenses`)
 * require `super_admin` server-side (`license:manage_platform`,
 * live-checked). Tenant-management methods (`activate`, `listDevices`,
 * `revokeDevice`) require `license:manage_tenant` (`agency_admin`).
 * `getStatus` requires only authentication — see its endpoint's own
 * docstring for why.
 */
@Injectable({ providedIn: 'root' })
export class LicenseService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getStatus(): Observable<LicenseStatusResponse> {
    return getLicenseStatusApiV1AdminLicenseStatusGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  activate(key: string): Observable<LicenseResponse> {
    return activateLicenseApiV1AdminLicenseActivatePost(this.http, this.config.rootUrl, {
      body: { key },
    }).pipe(map((response) => response.body));
  }

  listDevices(): Observable<LinkedDeviceResponse[]> {
    return listLinkedDevicesApiV1AdminLicenseDevicesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  revokeDevice(deviceId: string): Observable<void> {
    return revokeLinkedDeviceApiV1AdminLicenseDevicesDeviceIdRevokePatch(
      this.http,
      this.config.rootUrl,
      { device_id: deviceId },
    ).pipe(map(() => undefined));
  }

  issueLicense(
    tenantId: string,
    planTier: string,
    validityDays = 365,
    deviceCaps: Record<string, number | null> | null = null,
  ): Observable<IssuedLicenseResponse> {
    return issueLicenseApiV1AdminLicensePost(this.http, this.config.rootUrl, {
      body: {
        tenant_id: tenantId,
        plan_tier: planTier,
        validity_days: validityDays,
        device_caps: deviceCaps,
      },
    }).pipe(map((response) => response.body));
  }

  listLicenses(): Observable<LicenseResponse[]> {
    return listLicensesApiV1AdminLicenseGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  revokeLicense(tenantId: string): Observable<void> {
    return revokeLicenseApiV1AdminLicenseTenantIdRevokePatch(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
    }).pipe(map(() => undefined));
  }

  setPlanTier(tenantId: string, planTier: string): Observable<void> {
    return setLicensePlanTierApiV1AdminLicenseTenantIdPlanTierPatch(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
      body: { plan_tier: planTier },
    }).pipe(map(() => undefined));
  }

  setDeviceCap(tenantId: string, appType: string, maxDevices: number | null): Observable<void> {
    return setLicenseDeviceCapApiV1AdminLicenseTenantIdDeviceCapsAppTypePatch(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, app_type: appType, body: { max_devices: maxDevices } },
    ).pipe(map(() => undefined));
  }

  setFeatureOverride(tenantId: string, featureKey: string, granted: boolean): Observable<void> {
    return setLicenseFeatureOverrideApiV1AdminLicenseTenantIdFeatureOverridesKeyPut(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, key: featureKey, body: { granted } },
    ).pipe(map(() => undefined));
  }
}
