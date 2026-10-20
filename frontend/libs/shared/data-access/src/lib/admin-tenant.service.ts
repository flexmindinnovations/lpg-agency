import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getSetupProgressApiV1AdminSetupProgressGet } from './generated/fn/administration/get-setup-progress-api-v-1-admin-setup-progress-get';
import { getTenantApiV1AdminTenantGet } from './generated/fn/administration/get-tenant-api-v-1-admin-tenant-get';
import { renameTenantApiV1AdminTenantRenamePatch } from './generated/fn/administration/rename-tenant-api-v-1-admin-tenant-rename-patch';
import type { SetupProgressResponse } from './generated/models/setup-progress-response';
import type { TenantResponse } from './generated/models/tenant-response';

/** Thin wrapper over the generated `/admin/tenant` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminTenantService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getTenant(): Observable<TenantResponse> {
    return getTenantApiV1AdminTenantGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  renameTenant(name: string): Observable<TenantResponse> {
    return renameTenantApiV1AdminTenantRenamePatch(this.http, this.config.rootUrl, {
      body: { name },
    }).pipe(map((response) => response.body));
  }

  /** First-time setup checklist for Home (DA-32); needs `tenant:configure`. */
  getSetupProgress(): Observable<SetupProgressResponse> {
    return getSetupProgressApiV1AdminSetupProgressGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }
}
