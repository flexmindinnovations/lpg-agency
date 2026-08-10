import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getTenantApiV1AdminTenantGet } from './generated/fn/administration/get-tenant-api-v-1-admin-tenant-get';
import { renameTenantApiV1AdminTenantRenamePatch } from './generated/fn/administration/rename-tenant-api-v-1-admin-tenant-rename-patch';
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
}
