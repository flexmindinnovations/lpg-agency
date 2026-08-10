import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getEffectiveTenantConfigurationApiV1AdminTenantConfigurationEffectiveGet } from './generated/fn/administration/get-effective-tenant-configuration-api-v-1-admin-tenant-configuration-effective-get';
import { listTenantConfigurationApiV1AdminTenantConfigurationGet } from './generated/fn/administration/list-tenant-configuration-api-v-1-admin-tenant-configuration-get';
import { setTenantConfigurationApiV1AdminTenantConfigurationPost } from './generated/fn/administration/set-tenant-configuration-api-v-1-admin-tenant-configuration-post';
import type { TenantConfigurationResponse } from './generated/models/tenant-configuration-response';

/** Thin wrapper over the generated `/admin/tenant-configuration` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminTenantConfigurationService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listConfiguration(): Observable<TenantConfigurationResponse[]> {
    return listTenantConfigurationApiV1AdminTenantConfigurationGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((response) => response.body));
  }

  setConfiguration(
    configKey: string,
    configValue: unknown,
    effectiveFrom: string | null = null,
  ): Observable<TenantConfigurationResponse> {
    return setTenantConfigurationApiV1AdminTenantConfigurationPost(this.http, this.config.rootUrl, {
      body: { config_key: configKey, config_value: configValue, effective_from: effectiveFrom },
    }).pipe(map((response) => response.body));
  }

  getEffectiveConfiguration(configKey: string): Observable<TenantConfigurationResponse | null> {
    return getEffectiveTenantConfigurationApiV1AdminTenantConfigurationEffectiveGet(
      this.http,
      this.config.rootUrl,
      { config_key: configKey },
    ).pipe(map((response) => response.body));
  }
}
