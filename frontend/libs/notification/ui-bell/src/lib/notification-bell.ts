import { Component, EventEmitter, Output, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService, NotifyService, WebSocketService } from '@lpg/shared/data-access';
import { interval, startWith } from 'rxjs';
import { OverlayBadge } from 'primeng/overlaybadge';
import { ButtonDirective } from 'primeng/button';

/** `notification.new` over the realtime socket (`realtime_handlers.py`). */
interface NewNotificationMessage {
  type: 'notification.new';
  notification_id: string;
  title?: string;
  body?: string;
}

@Component({
  selector: 'lib-notification-bell',
  imports: [OverlayBadge, ButtonDirective],
  templateUrl: './notification-bell.html',
  styleUrl: './notification-bell.css',
})
export class NotificationBell {
  private readonly notificationService = inject(NotificationService);
  private readonly wsService = inject(WebSocketService);
  private readonly notify = inject(NotifyService);

  @Output() toggled = new EventEmitter<void>();

  /** Shared with the drawer and the notifications page — marking anything
   *  read anywhere updates this badge instantly. */
  readonly unreadCount = this.notificationService.unreadCount;

  constructor() {
    this.wsService.subscribeTo('notifications');

    // A new notification arrived — show it, bump immediately, then
    // reconcile. The bell is in the app shell, so this toast shows on
    // whatever page the user is on.
    this.wsService
      .on<NewNotificationMessage>('notification.new')
      .pipe(takeUntilDestroyed())
      .subscribe((message) => {
        if (message.body) this.notify.info(message.body, message.title ?? 'Notification');
        this.notificationService.adjustUnreadCount(1);
        this.notificationService.refreshUnreadCount();
      });

    // Initial load + a slow safety-net poll (real-time paths cover the rest).
    interval(300000)
      .pipe(startWith(0), takeUntilDestroyed())
      .subscribe(() => this.notificationService.refreshUnreadCount());
  }
}
