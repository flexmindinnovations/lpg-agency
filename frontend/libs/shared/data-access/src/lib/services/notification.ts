import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from '../generated/api-configuration';
import { getUnreadCountApiV1NotificationsUnreadCountGet } from '../generated/fn/notifications/get-unread-count-api-v-1-notifications-unread-count-get';
import { listNotificationsApiV1NotificationsGet } from '../generated/fn/notifications/list-notifications-api-v-1-notifications-get';
import { markAllReadApiV1NotificationsReadAllPost } from '../generated/fn/notifications/mark-all-read-api-v-1-notifications-read-all-post';
import { markReadApiV1NotificationsIdReadPatch } from '../generated/fn/notifications/mark-read-api-v-1-notifications-id-read-patch';
import type { PaginatedNotificationResponse } from '../generated/models/paginated-notification-response';
import type { UnreadCountResponse } from '../generated/models/unread-count-response';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(skip = 0, limit = 50, unreadOnly = false): Observable<PaginatedNotificationResponse> {
    return listNotificationsApiV1NotificationsGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      unread_only: unreadOnly,
    }).pipe(map((res) => res.body));
  }

  getUnreadCount(): Observable<UnreadCountResponse> {
    return getUnreadCountApiV1NotificationsUnreadCountGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  markRead(id: string): Observable<void> {
    return markReadApiV1NotificationsIdReadPatch(this.http, this.config.rootUrl, {
      id,
    }).pipe(map(() => undefined));
  }

  markAllRead(): Observable<void> {
    return markAllReadApiV1NotificationsReadAllPost(this.http, this.config.rootUrl).pipe(
      map(() => undefined),
    );
  }
}
