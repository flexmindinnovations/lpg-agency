import { Component, EventEmitter, Output, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService, WebSocketService } from '@lpg/shared/data-access';
import { interval, startWith } from 'rxjs';
import { BadgeModule } from 'primeng/badge';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'lib-notification-bell',
  imports: [BadgeModule, ButtonModule],
  templateUrl: './notification-bell.html',
  styleUrl: './notification-bell.css'
})
export class NotificationBell {
  private readonly notificationService = inject(NotificationService);
  private readonly wsService = inject(WebSocketService);

  @Output() toggled = new EventEmitter<void>();

  /** Shared with the drawer and the notifications page — marking anything
   *  read anywhere updates this badge instantly. */
  readonly unreadCount = this.notificationService.unreadCount;

  constructor() {
    this.wsService.subscribeTo('notifications');

    // A new notification arrived — bump immediately, then reconcile.
    this.wsService.on('notification.new')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        this.notificationService.adjustUnreadCount(1);
        this.notificationService.refreshUnreadCount();
      });

    // Initial load + a slow safety-net poll (real-time paths cover the rest).
    interval(300000)
      .pipe(startWith(0), takeUntilDestroyed())
      .subscribe(() => this.notificationService.refreshUnreadCount());
  }
}
