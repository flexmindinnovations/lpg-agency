import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject, debounceTime, map, tap } from 'rxjs';
import { WebSocketService } from '../websocket.service';
import { ApiConfiguration } from '../generated/api-configuration';
import { getUnreadCountApiV1NotificationsUnreadCountGet } from '../generated/fn/notifications/get-unread-count-api-v-1-notifications-unread-count-get';
import { listNotificationsApiV1NotificationsGet } from '../generated/fn/notifications/list-notifications-api-v-1-notifications-get';
import { markAllReadApiV1NotificationsReadAllPost } from '../generated/fn/notifications/mark-all-read-api-v-1-notifications-read-all-post';
import { markReadApiV1NotificationsIdReadPatch } from '../generated/fn/notifications/mark-read-api-v-1-notifications-id-read-patch';
import type { NotificationResponse } from '../generated/models/notification-response';
import type { PaginatedNotificationResponse } from '../generated/models/paginated-notification-response';
import type { UnreadCountResponse } from '../generated/models/unread-count-response';

/** Where a notification leads: router commands plus optional query params. */
export interface NotificationLink {
  readonly commands: string[];
  readonly queryParams?: Record<string, string>;
}

/** `notification.new` over the realtime socket (`realtime_handlers.py`). */
export interface NewNotificationMessage {
  type: 'notification.new';
  notification_id: string;
  notification_type?: string;
  title?: string;
  body?: string;
  reference_type?: string | null;
  reference_id?: string | null;
  created_at?: string;
}

export interface NotificationDayGroup {
  /** `Today`, `Yesterday`, or e.g. `Mon, 12 Oct`. */
  readonly label: string;
  readonly items: NotificationResponse[];
}

/**
 * Newest-first notifications grouped by the local calendar day they
 * arrived on — the inbox's sections.
 */
export function groupNotificationsByDay(
  items: readonly NotificationResponse[],
  now: Date = new Date(),
): NotificationDayGroup[] {
  const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  const today = dayKey(now);
  const yesterdayDate = new Date(now);
  yesterdayDate.setDate(now.getDate() - 1);
  const yesterday = dayKey(yesterdayDate);
  const sameYear = (d: Date) => d.getFullYear() === now.getFullYear();

  const groups: { key: string; label: string; items: NotificationResponse[] }[] = [];
  for (const item of items) {
    const created = new Date(item.created_at);
    const key = dayKey(created);
    let group = groups.find((g) => g.key === key);
    if (!group) {
      const label =
        key === today
          ? 'Today'
          : key === yesterday
            ? 'Yesterday'
            : created.toLocaleDateString('en-IN', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                ...(sameYear(created) ? {} : { year: 'numeric' }),
              });
      group = { key, label, items: [] };
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups.map(({ label, items: groupItems }) => ({ label, items: groupItems }));
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);
  private readonly ws = inject(WebSocketService);
  private realtimeStarted = false;

  private readonly changedSubject = new Subject<void>();
  /**
   * The user's notifications changed somewhere — a new one arrived, or one
   * was read in another tab or on another device, or the socket came back
   * after a drop. Lists showing notifications reload on it.
   */
  readonly changed$ = this.changedSubject.pipe(debounceTime(150));
  private readonly arrivedSubject = new Subject<NewNotificationMessage>();
  /** Each new notification as it arrives (for the toast). */
  readonly arrived$ = this.arrivedSubject.asObservable();

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

  /**
   * Listen on the user's realtime channel once per app: keep the badge
   * exact and tell open lists to reload. Called by the shell's bell.
   */
  startRealtime(): void {
    if (this.realtimeStarted) return;
    this.realtimeStarted = true;
    this.ws.subscribeTo('notifications');
    this.ws.messages$.subscribe((message) => {
      switch (message.type) {
        case 'notification.new':
          this.adjustUnreadCount(1);
          this.arrivedSubject.next(message as NewNotificationMessage);
          this.changedSubject.next();
          break;
        case 'notification.read':
        case 'notification.read_all':
          // Read in another tab or device: re-fetch rather than guess,
          // since this tab may already have counted it.
          this.refreshUnreadCount();
          this.changedSubject.next();
          break;
      }
    });
    // Anything that arrived while the socket was down.
    this.ws.reconnected$.subscribe(() => {
      this.refreshUnreadCount();
      this.changedSubject.next();
    });
  }

  /** Re-fetch the authoritative unread count into the shared signal. */
  refreshUnreadCount(): void {
    this.getUnreadCount().subscribe({
      next: (res) => this._unreadCount.set(Math.max(0, res.count ?? 0)),
      // Deliberately silent, not a toast — this is a background poll (every
      // few minutes, see NotificationBell), and a toast on every transient
      // network blip would be worse than the badge just staying stale.
      // Logged rather than left fully uncaught, which otherwise threw an
      // async error into the console on every failed poll.
      error: (err) => console.debug('refreshUnreadCount failed', err),
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
   * Where a notification leads, from its `reference_type` / `reference_id`.
   * `null` when there's nothing specific to open.
   */
  routeFor(
    notification: Pick<NotificationResponse, 'reference_type' | 'reference_id'>,
  ): NotificationLink | null {
    const id = notification.reference_id ?? null;
    switch (notification.reference_type) {
      case 'order':
        return { commands: id ? ['/orders', id] : ['/orders'] };
      case 'complaint':
        return id
          ? { commands: ['/complaints'], queryParams: { complaint: id } }
          : { commands: ['/complaints'] };
      case 'route':
      case 'cash_handover':
        return { commands: ['/dispatch'] };
      case 'invoice':
        return { commands: ['/invoices'] };
      case 'inventory_location':
        return { commands: ['/inventory'] };
      case 'compliance_document':
        return { commands: ['/compliance-calendar'] };
      case 'price_list_proposal':
        return { commands: ['/admin/price-lists'] };
      default:
        return null;
    }
  }
}
