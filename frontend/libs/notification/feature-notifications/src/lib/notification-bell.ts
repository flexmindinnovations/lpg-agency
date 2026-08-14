import { Component, EventEmitter, Output, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService } from '@lpg/shared/data-access';
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

  @Output() toggle = new EventEmitter<void>();

  unreadCount = signal<number>(0);

  constructor() {
    interval(60000)
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
