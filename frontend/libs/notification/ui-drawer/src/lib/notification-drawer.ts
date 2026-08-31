import { Component, effect, inject, model, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { DrawerModule } from 'primeng/drawer';
import { ButtonModule } from 'primeng/button';
import { BadgeModule } from 'primeng/badge';
import { TooltipModule } from 'primeng/tooltip';
import { NotificationService } from '@lpg/shared/data-access';
import type { NotificationResponse } from '@lpg/shared/data-access';

@Component({
  selector: 'lib-notification-drawer',
  imports: [DatePipe, RouterLink, DrawerModule, ButtonModule, BadgeModule, TooltipModule],
  templateUrl: './notification-drawer.html',
  styleUrl: './notification-drawer.css'
})
export class NotificationDrawer {
  private readonly notificationService = inject(NotificationService);
  private readonly router = inject(Router);

  /** Two-way bound from the shell. A signal (not a plain `@Input`) so the
   *  `effect` below actually re-runs when the drawer is opened — otherwise
   *  it only ever loaded once, at construction, while closed. */
  readonly visible = model(false);

  notifications = signal<NotificationResponse[]>([]);

  protected hasLink(n: NotificationResponse): boolean {
    return this.notificationService.routeFor(n) !== null;
  }

  constructor() {
    effect(() => {
      if (this.visible()) {
        this.loadNotifications();
      }
    });
  }

  loadNotifications() {
    this.notificationService.list(0, 10).subscribe({
      next: (res) => {
        this.notifications.set(res.items);
      }
    });
  }

  markAsRead(id: string) {
    this.notificationService.markRead(id).subscribe({
      next: () => {
        this.loadNotifications();
      }
    });
  }

  /** Click a notification: mark it read, then jump to what it references. */
  open(notification: NotificationResponse) {
    const route = this.notificationService.routeFor(notification);
    if (!notification.is_read) {
      this.notificationService.markRead(notification.id).subscribe();
    }
    if (route) {
      this.visible.set(false);
      void this.router.navigate(route);
    }
  }

  onHide() {
    this.visible.set(false);
  }
}
