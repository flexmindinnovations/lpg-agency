import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listAuditLogApiV1AdminAuditLogGet } from './generated/fn/administration/list-audit-log-api-v-1-admin-audit-log-get';
import type { AuditLogPageResponse } from './generated/models/audit-log-page-response';

/** Thin wrapper over the generated `/admin/audit-log` client function. */
@Injectable({ providedIn: 'root' })
export class AdminAuditLogService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listAuditLog(options?: {
    entityName?: string | null;
    actorId?: string | null;
    cursor?: string | null;
    limit?: number;
  }): Observable<AuditLogPageResponse> {
    return listAuditLogApiV1AdminAuditLogGet(this.http, this.config.rootUrl, {
      entity_name: options?.entityName,
      actor_id: options?.actorId,
      cursor: options?.cursor,
      limit: options?.limit,
    }).pipe(map((response) => response.body));
  }
}
