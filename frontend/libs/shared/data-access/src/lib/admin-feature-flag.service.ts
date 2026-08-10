import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { createFeatureFlagApiV1AdminFeatureFlagsPost } from './generated/fn/administration/create-feature-flag-api-v-1-admin-feature-flags-post';
import { isFeatureFlagEnabledApiV1AdminFeatureFlagsKeyEnabledGet } from './generated/fn/administration/is-feature-flag-enabled-api-v-1-admin-feature-flags-key-enabled-get';
import { listFeatureFlagsApiV1AdminFeatureFlagsGet } from './generated/fn/administration/list-feature-flags-api-v-1-admin-feature-flags-get';
import { scheduleFeatureFlagApiV1AdminFeatureFlagsKeySchedulePatch } from './generated/fn/administration/schedule-feature-flag-api-v-1-admin-feature-flags-key-schedule-patch';
import { setFeatureFlagEnabledByDefaultApiV1AdminFeatureFlagsKeyEnabledByDefaultPatch } from './generated/fn/administration/set-feature-flag-enabled-by-default-api-v-1-admin-feature-flags-key-enabled-by-default-patch';
import { setFeatureFlagOverrideApiV1AdminFeatureFlagsOverridesKeyPut } from './generated/fn/administration/set-feature-flag-override-api-v-1-admin-feature-flags-overrides-key-put';
import { setFeatureFlagRolloutPercentageApiV1AdminFeatureFlagsKeyRolloutPatch } from './generated/fn/administration/set-feature-flag-rollout-percentage-api-v-1-admin-feature-flags-key-rollout-patch';
import type { FeatureFlagEnabledResponse } from './generated/models/feature-flag-enabled-response';
import type { FeatureFlagOverrideResponse } from './generated/models/feature-flag-override-response';
import type { FeatureFlagResponse } from './generated/models/feature-flag-response';

/**
 * Thin wrapper over the generated `/admin/feature-flags*` client functions.
 *
 * Platform-management methods (`createFlag`, `setEnabledByDefault`,
 * `setRolloutPercentage`, `schedule`) require `super_admin` server-side
 * (`feature_flags:manage_platform`, live-checked) — the Dashboard's own
 * permission-driven UI hides them for every other role, but the actual
 * enforcement is server-side regardless.
 */
@Injectable({ providedIn: 'root' })
export class AdminFeatureFlagService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listFlags(): Observable<FeatureFlagResponse[]> {
    return listFeatureFlagsApiV1AdminFeatureFlagsGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  createFlag(
    key: string,
    description: string,
    isEnabledByDefault = false,
    rolloutPercentage: number | null = null,
  ): Observable<FeatureFlagResponse> {
    return createFeatureFlagApiV1AdminFeatureFlagsPost(this.http, this.config.rootUrl, {
      body: {
        key,
        description,
        is_enabled_by_default: isEnabledByDefault,
        rollout_percentage: rolloutPercentage,
      },
    }).pipe(map((response) => response.body));
  }

  setEnabledByDefault(key: string, enabled: boolean): Observable<void> {
    return setFeatureFlagEnabledByDefaultApiV1AdminFeatureFlagsKeyEnabledByDefaultPatch(
      this.http,
      this.config.rootUrl,
      { key, body: { enabled } },
    ).pipe(map(() => undefined));
  }

  setRolloutPercentage(key: string, rolloutPercentage: number | null): Observable<void> {
    return setFeatureFlagRolloutPercentageApiV1AdminFeatureFlagsKeyRolloutPatch(
      this.http,
      this.config.rootUrl,
      { key, body: { rollout_percentage: rolloutPercentage } },
    ).pipe(map(() => undefined));
  }

  schedule(key: string, startsAt: string | null, endsAt: string | null): Observable<void> {
    return scheduleFeatureFlagApiV1AdminFeatureFlagsKeySchedulePatch(
      this.http,
      this.config.rootUrl,
      {
        key,
        body: { starts_at: startsAt, ends_at: endsAt },
      },
    ).pipe(map(() => undefined));
  }

  isEnabled(key: string): Observable<FeatureFlagEnabledResponse> {
    return isFeatureFlagEnabledApiV1AdminFeatureFlagsKeyEnabledGet(this.http, this.config.rootUrl, {
      key,
    }).pipe(map((response) => response.body));
  }

  setOverride(key: string, enabled: boolean): Observable<FeatureFlagOverrideResponse> {
    return setFeatureFlagOverrideApiV1AdminFeatureFlagsOverridesKeyPut(
      this.http,
      this.config.rootUrl,
      {
        key,
        body: { enabled },
      },
    ).pipe(map((response) => response.body));
  }
}
