import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listAuditLogApiV1AdminAuditLogGet } from './generated/fn/administration/list-audit-log-api-v-1-admin-audit-log-get';
import { listAuditLogEntityTypesApiV1AdminAuditLogEntityTypesGet } from './generated/fn/administration/list-audit-log-entity-types-api-v-1-admin-audit-log-entity-types-get';
import type { AuditLogPageResponse } from './generated/models/audit-log-page-response';

export type AuditLogAction = 'create' | 'update' | 'delete';

/** Thin wrapper over the generated `/admin/audit-log` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminAuditLogService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listAuditLog(options?: {
    entityName?: string | null;
    actorId?: string | null;
    action?: AuditLogAction | null;
    /** Inclusive lower bound, ISO-8601 instant. */
    dateFrom?: string | null;
    /** Exclusive upper bound, ISO-8601 instant. */
    dateTo?: string | null;
    cursor?: string | null;
    limit?: number;
  }): Observable<AuditLogPageResponse> {
    return listAuditLogApiV1AdminAuditLogGet(this.http, this.config.rootUrl, {
      entity_name: options?.entityName,
      actor_id: options?.actorId,
      action: options?.action,
      date_from: options?.dateFrom,
      date_to: options?.dateTo,
      cursor: options?.cursor,
      limit: options?.limit,
    }).pipe(map((response) => response.body));
  }

  /** Record types (table names) present in this agency's audit log. */
  listEntityTypes(): Observable<string[]> {
    return listAuditLogEntityTypesApiV1AdminAuditLogEntityTypesGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((response) => response.body));
  }
}
