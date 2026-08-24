import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { activateLicenseApiV1AdminLicenseActivatePost } from './generated/fn/administration/activate-license-api-v-1-admin-license-activate-post';
import { getLicenseStatusApiV1AdminLicenseStatusGet } from './generated/fn/administration/get-license-status-api-v-1-admin-license-status-get';
import { listLinkedDevicesApiV1AdminLicenseDevicesGet } from './generated/fn/administration/list-linked-devices-api-v-1-admin-license-devices-get';
import { revokeLinkedDeviceApiV1AdminLicenseDevicesDeviceIdRevokePatch } from './generated/fn/administration/revoke-linked-device-api-v-1-admin-license-devices-device-id-revoke-patch';
import { activateLicenseApiV1PlatformLicenseTenantIdActivatePost } from './generated/fn/platform-console/activate-license-api-v-1-platform-license-tenant-id-activate-post';
import { issueLicenseApiV1PlatformLicensePost } from './generated/fn/platform-console/issue-license-api-v-1-platform-license-post';
import { listLicensesApiV1PlatformLicenseGet } from './generated/fn/platform-console/list-licenses-api-v-1-platform-license-get';
import { revokeLicenseApiV1PlatformLicenseTenantIdRevokePatch } from './generated/fn/platform-console/revoke-license-api-v-1-platform-license-tenant-id-revoke-patch';
import { setLicenseDeviceCapApiV1PlatformLicenseTenantIdDeviceCapsAppTypePatch } from './generated/fn/platform-console/set-license-device-cap-api-v-1-platform-license-tenant-id-device-caps-app-type-patch';
import { setLicenseFeatureOverrideApiV1PlatformLicenseTenantIdFeatureOverridesKeyPut } from './generated/fn/platform-console/set-license-feature-override-api-v-1-platform-license-tenant-id-feature-overrides-key-put';
import { setLicensePlanTierApiV1PlatformLicenseTenantIdPlanTierPatch } from './generated/fn/platform-console/set-license-plan-tier-api-v-1-platform-license-tenant-id-plan-tier-patch';
import type { IssuedLicenseResponse } from './generated/models/issued-license-response';
import type { LicenseResponse } from './generated/models/license-response';
import type { LicenseStatusResponse } from './generated/models/license-status-response';
import type { LinkedDeviceResponse } from './generated/models/linked-device-response';

/**
 * Thin wrapper over the generated `/admin/license*` and `/platform/license*`
 * client functions.
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
    return issueLicenseApiV1PlatformLicensePost(this.http, this.config.rootUrl, {
      body: {
        tenant_id: tenantId,
        plan_tier: planTier,
        validity_days: validityDays,
        device_caps: deviceCaps,
      },
    }).pipe(map((response) => response.body));
  }

  listLicenses(): Observable<LicenseResponse[]> {
    return listLicensesApiV1PlatformLicenseGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  /** Lets a `super_admin` activate a license on a tenant's behalf, right
   * after issuing it — the platform-tier sibling of `activate()` above,
   * which is tenant self-service only. */
  activateOnBehalfOf(tenantId: string, key: string): Observable<LicenseResponse> {
    return activateLicenseApiV1PlatformLicenseTenantIdActivatePost(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
      body: { key },
    }).pipe(map((response) => response.body));
  }

  revokeLicense(tenantId: string): Observable<void> {
    return revokeLicenseApiV1PlatformLicenseTenantIdRevokePatch(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
    }).pipe(map(() => undefined));
  }

  setPlanTier(tenantId: string, planTier: string): Observable<void> {
    return setLicensePlanTierApiV1PlatformLicenseTenantIdPlanTierPatch(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, body: { plan_tier: planTier } },
    ).pipe(map(() => undefined));
  }

  setDeviceCap(tenantId: string, appType: string, maxDevices: number | null): Observable<void> {
    return setLicenseDeviceCapApiV1PlatformLicenseTenantIdDeviceCapsAppTypePatch(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, app_type: appType, body: { max_devices: maxDevices } },
    ).pipe(map(() => undefined));
  }

  setFeatureOverride(tenantId: string, featureKey: string, granted: boolean): Observable<void> {
    return setLicenseFeatureOverrideApiV1PlatformLicenseTenantIdFeatureOverridesKeyPut(
      this.http,
      this.config.rootUrl,
      { tenant_id: tenantId, key: featureKey, body: { granted } },
    ).pipe(map(() => undefined));
  }
}
