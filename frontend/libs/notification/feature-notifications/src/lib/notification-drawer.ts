import { Component, EventEmitter, Input, Output, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DrawerModule } from 'primeng/drawer';
import { ButtonModule } from 'primeng/button';
import { BadgeModule } from 'primeng/badge';
import { TooltipModule } from 'primeng/tooltip';
import { NotificationService } from '@lpg/shared/data-access';
import type { NotificationResponse } from '@lpg/shared/data-access';

@Component({
  selector: 'lpg-notification-drawer',
  imports: [CommonModule, RouterLink, DrawerModule, ButtonModule, BadgeModule, TooltipModule],
  templateUrl: './notification-drawer.html',
  styleUrl: './notification-drawer.css'
})
export class NotificationDrawer {
  private readonly notificationService = inject(NotificationService);

  @Input() visible = false;
  @Output() visibleChange = new EventEmitter<boolean>();

  notifications = signal<NotificationResponse[]>([]);

  constructor() {
    effect(() => {
      if (this.visible) {
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

  onHide() {
    this.visibleChange.emit(false);
  }
}
