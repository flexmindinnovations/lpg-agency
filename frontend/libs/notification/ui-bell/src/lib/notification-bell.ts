import { Component, EventEmitter, Output, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService, NotifyService } from '@lpg/shared/data-access';
import { interval, startWith } from 'rxjs';
import { OverlayBadge } from 'primeng/overlaybadge';
import { ButtonDirective } from 'primeng/button';

@Component({
  selector: 'lib-notification-bell',
  imports: [OverlayBadge, ButtonDirective],
  templateUrl: './notification-bell.html',
  styleUrl: './notification-bell.css',
})
export class NotificationBell {
  private readonly notificationService = inject(NotificationService);
  private readonly notify = inject(NotifyService);

  @Output() toggled = new EventEmitter<void>();

  /** Shared with the drawer and the notifications page — marking anything
   *  read anywhere (this tab, another tab, another device) updates this
   *  badge instantly. */
  readonly unreadCount = this.notificationService.unreadCount;

  constructor() {
    // The bell lives in the app shell, so this is where the user's realtime
    // channel is opened, and the toast shows on whatever page they're on.
    this.notificationService.startRealtime();
    this.notificationService.arrived$.pipe(takeUntilDestroyed()).subscribe((message) => {
      if (message.body) this.notify.info(message.body, message.title ?? 'Notification');
    });

    // Initial load + a slow safety net; realtime covers the rest, and a
    // reconnect re-syncs the count on its own.
    interval(300000)
      .pipe(startWith(0), takeUntilDestroyed())
      .subscribe(() => this.notificationService.refreshUnreadCount());
  }
}
