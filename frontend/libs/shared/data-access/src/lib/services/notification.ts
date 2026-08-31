import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, tap } from 'rxjs';
import { ApiConfiguration } from '../generated/api-configuration';
import { getUnreadCountApiV1NotificationsUnreadCountGet } from '../generated/fn/notifications/get-unread-count-api-v-1-notifications-unread-count-get';
import { listNotificationsApiV1NotificationsGet } from '../generated/fn/notifications/list-notifications-api-v-1-notifications-get';
import { markAllReadApiV1NotificationsReadAllPost } from '../generated/fn/notifications/mark-all-read-api-v-1-notifications-read-all-post';
import { markReadApiV1NotificationsIdReadPatch } from '../generated/fn/notifications/mark-read-api-v-1-notifications-id-read-patch';
import type { NotificationResponse } from '../generated/models/notification-response';
import type { PaginatedNotificationResponse } from '../generated/models/paginated-notification-response';
import type { UnreadCountResponse } from '../generated/models/unread-count-response';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /** The single source of truth for the unread badge. The bell renders it;
   *  every read/mark-all/new-notification path keeps it current so the
   *  count changes the instant the user acts, not on the next poll. */
  private readonly _unreadCount = signal(0);
  readonly unreadCount = this._unreadCount.asReadonly();

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

  /** Re-fetch the authoritative unread count into the shared signal. */
  refreshUnreadCount(): void {
    this.getUnreadCount().subscribe({
      next: (res) => this._unreadCount.set(Math.max(0, res.count ?? 0)),
    });
  }

  /** Nudge the count locally (e.g. +1 on a `notification.new` event). */
  adjustUnreadCount(delta: number): void {
    this._unreadCount.update((c) => Math.max(0, c + delta));
  }

  markRead(id: string): Observable<void> {
    return markReadApiV1NotificationsIdReadPatch(this.http, this.config.rootUrl, {
      id,
    }).pipe(
      map(() => undefined),
      // Optimistic, then reconcile — the badge drops immediately and a
      // background fetch corrects it if this was already read.
      tap(() => {
        this.adjustUnreadCount(-1);
        this.refreshUnreadCount();
      }),
    );
  }

  markAllRead(): Observable<void> {
    return markAllReadApiV1NotificationsReadAllPost(this.http, this.config.rootUrl).pipe(
      map(() => undefined),
      tap(() => this._unreadCount.set(0)),
    );
  }

  /**
   * The in-app route a notification points at, from its
   * `reference_type` / `reference_id`. `null` when there's nothing
   * specific to open.
   */
  routeFor(notification: NotificationResponse): string[] | null {
    const id = notification.reference_id;
    switch (notification.reference_type) {
      case 'order':
        return id ? ['/orders', id] : ['/orders'];
      case 'invoice':
        return ['/invoices'];
      case 'complaint':
        return ['/complaints'];
      default:
        return null;
    }
  }
}
