import { Component, EventEmitter, Output, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService, WebSocketService } from '@lpg/shared/data-access';
import { interval, startWith, switchMap } from 'rxjs';
import { BadgeModule } from 'primeng/badge';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'lpg-notification-bell',
  imports: [BadgeModule, ButtonModule],
  templateUrl: './notification-bell.html',
  styleUrl: './notification-bell.css'
})
export class NotificationBell {
  private readonly notificationService = inject(NotificationService);

  private readonly wsService = inject(WebSocketService);

  @Output() toggle = new EventEmitter<void>();

  unreadCount = signal<number>(0);

  constructor() {
    this.wsService.subscribeTo('notifications');

    // Real-time updates
    this.wsService.on('notification.new')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        // Optimistic update
        this.unreadCount.update(c => c + 1);
      });

    // Fallback polling (less frequent now, every 5 mins) and initial fetch
    interval(300000)
      .pipe(
        startWith(0),
        switchMap(() => this.notificationService.getUnreadCount()),
        takeUntilDestroyed()
      )
      .subscribe((res) => {
        this.unreadCount.set(res.count ?? 0);
      });
  }
}
