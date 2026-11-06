import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { activateLicenseApiV1AdminLicenseActivatePost } from './generated/fn/administration/activate-license-api-v-1-admin-license-activate-post';
import { getLicenseStatusApiV1AdminLicenseStatusGet } from './generated/fn/administration/get-license-status-api-v-1-admin-license-status-get';
import { approveDeviceApiV1AdminLicenseDevicesDeviceIdApprovePost } from './generated/fn/linked-devices/approve-device-api-v-1-admin-license-devices-device-id-approve-post';
import { blockDeviceApiV1AdminLicenseDevicesDeviceIdBlockPost } from './generated/fn/linked-devices/block-device-api-v-1-admin-license-devices-device-id-block-post';
import { countPendingDevicesApiV1AdminLicenseDevicesPendingCountGet } from './generated/fn/linked-devices/count-pending-devices-api-v-1-admin-license-devices-pending-count-get';
import { getDeviceHistoryApiV1AdminLicenseDevicesDeviceIdHistoryGet } from './generated/fn/linked-devices/get-device-history-api-v-1-admin-license-devices-device-id-history-get';
import { listLinkedDevicesApiV1AdminLicenseDevicesGet } from './generated/fn/linked-devices/list-linked-devices-api-v-1-admin-license-devices-get';
import { removeDeviceApiV1AdminLicenseDevicesDeviceIdRemovePost } from './generated/fn/linked-devices/remove-device-api-v-1-admin-license-devices-device-id-remove-post';
import { unblockDeviceApiV1AdminLicenseDevicesDeviceIdUnblockPost } from './generated/fn/linked-devices/unblock-device-api-v-1-admin-license-devices-device-id-unblock-post';
import { updateDeviceApiV1AdminLicenseDevicesDeviceIdPatch } from './generated/fn/linked-devices/update-device-api-v-1-admin-license-devices-device-id-patch';
import { replaceLicenseKeyApiV1PlatformLicenseTenantIdKeyPost } from './generated/fn/platform-console/replace-license-key-api-v-1-platform-license-tenant-id-key-post';
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
import type { DeviceHistoryEntryResponse } from './generated/models/device-history-entry-response';
import type { DeviceStatus } from './generated/models/device-status';
import type { LinkedDeviceResponse } from './generated/models/linked-device-response';

export interface DeviceFilters {
  readonly appType?: 'driver_app' | 'admin_app' | null;
  readonly status?: DeviceStatus | null;
}

/**
 * Thin wrapper over the generated `/admin/license*` and `/platform/license*`
 * client functions.
 *
 * Platform-management methods (`issueLicense`, `revokeLicense`,
 * `setPlanTier`, `setDeviceCap`, `setFeatureOverride`, `listLicenses`)
 * require `super_admin` server-side (`license:manage_platform`,
 * live-checked). Tenant-management methods (`activate` and the device methods) require `license:manage_tenant` (`agency_admin`).
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

  /** Phones using the Driver and Admin apps. With no `status`, every phone
   * still in use (not removed). */
  listDevices(filters: DeviceFilters = {}): Observable<LinkedDeviceResponse[]> {
    return listLinkedDevicesApiV1AdminLicenseDevicesGet(this.http, this.config.rootUrl, {
      app_type: filters.appType ?? null,
      status: filters.status ?? null,
    }).pipe(map((response) => response.body));
  }

  pendingDeviceCount(): Observable<number> {
    return countPendingDevicesApiV1AdminLicenseDevicesPendingCountGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((response) => response.body.count));
  }

  deviceHistory(deviceId: string): Observable<DeviceHistoryEntryResponse[]> {
    return getDeviceHistoryApiV1AdminLicenseDevicesDeviceIdHistoryGet(
      this.http,
      this.config.rootUrl,
      { device_id: deviceId },
    ).pipe(map((response) => response.body));
  }

  approveDevice(deviceId: string): Observable<LinkedDeviceResponse> {
    return approveDeviceApiV1AdminLicenseDevicesDeviceIdApprovePost(
      this.http,
      this.config.rootUrl,
      { device_id: deviceId },
    ).pipe(map((response) => response.body));
  }

  blockDevice(deviceId: string): Observable<LinkedDeviceResponse> {
    return blockDeviceApiV1AdminLicenseDevicesDeviceIdBlockPost(this.http, this.config.rootUrl, {
      device_id: deviceId,
    }).pipe(map((response) => response.body));
  }

  unblockDevice(deviceId: string): Observable<LinkedDeviceResponse> {
    return unblockDeviceApiV1AdminLicenseDevicesDeviceIdUnblockPost(
      this.http,
      this.config.rootUrl,
      { device_id: deviceId },
    ).pipe(map((response) => response.body));
  }

  removeDevice(deviceId: string): Observable<LinkedDeviceResponse> {
    return removeDeviceApiV1AdminLicenseDevicesDeviceIdRemovePost(this.http, this.config.rootUrl, {
      device_id: deviceId,
    }).pipe(map((response) => response.body));
  }

  /** Only the fields given change; an empty `assetNote` clears the note. */
  updateDevice(
    deviceId: string,
    changes: { displayName?: string; assetNote?: string },
  ): Observable<LinkedDeviceResponse> {
    const body: { display_name?: string; asset_note?: string } = {};
    if (changes.displayName !== undefined) body.display_name = changes.displayName;
    if (changes.assetNote !== undefined) body.asset_note = changes.assetNote;
    return updateDeviceApiV1AdminLicenseDevicesDeviceIdPatch(this.http, this.config.rootUrl, {
      device_id: deviceId,
      body,
    }).pipe(map((response) => response.body));
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

  /** Issues a fresh key for a licence still pending activation — the old
   * key stops working. For when the shown-once key was lost (DA-09). */
  replaceKey(tenantId: string): Observable<IssuedLicenseResponse> {
    return replaceLicenseKeyApiV1PlatformLicenseTenantIdKeyPost(this.http, this.config.rootUrl, {
      tenant_id: tenantId,
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
