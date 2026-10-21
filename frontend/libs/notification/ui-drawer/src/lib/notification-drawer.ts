import { Component, computed, effect, inject, model, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { DrawerModule } from 'primeng/drawer';
import { ButtonDirective } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';
import { DrawerA11yDirective, EmptyStateComponent } from '@lpg/shared/ui';
import {
  NotificationService,
  NotifyService,
  errorMessageFor,
  groupNotificationsByDay,
} from '@lpg/shared/data-access';
import type { NotificationResponse } from '@lpg/shared/data-access';

@Component({
  selector: 'lib-notification-drawer',
  imports: [
    DatePipe,
    RouterLink,
    DrawerModule,
    DrawerA11yDirective,
    EmptyStateComponent,
    ButtonDirective,
    TooltipModule,
  ],
  templateUrl: './notification-drawer.html',
  styleUrl: './notification-drawer.css',
})
export class NotificationDrawer {
  private readonly notificationService = inject(NotificationService);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);

  /** Two-way bound from the shell. A signal (not a plain `@Input`) so the
   *  `effect` below actually re-runs when the drawer is opened — otherwise
   *  it only ever loaded once, at construction, while closed. */
  readonly visible = model(false);

  notifications = signal<NotificationResponse[]>([]);

  /** IDs the user has cleared from *this* drawer view. Never sent to the
   *  server — the notifications still exist and still show on the
   *  /notifications page; they're just hidden here until a page reload or
   *  a genuinely new notification arrives. */
  private readonly dismissed = signal<ReadonlySet<string>>(new Set());

  readonly visibleNotifications = computed(() =>
    this.notifications().filter((n) => !this.dismissed().has(n.id)),
  );

  /** Sections for the list: Today, Yesterday, then dated days. */
  readonly groups = computed(() => groupNotificationsByDay(this.visibleNotifications()));

  readonly hasUnread = computed(() => this.visibleNotifications().some((n) => !n.is_read));

  protected hasLink(n: NotificationResponse): boolean {
    return this.notificationService.routeFor(n) !== null;
  }

  /** Hide every notification currently in the drawer. View-only — the
   *  server list is untouched. */
  clearAll(): void {
    const next = new Set(this.dismissed());
    for (const n of this.notifications()) {
      next.add(n.id);
    }
    this.dismissed.set(next);
  }

  constructor() {
    effect(() => {
      if (this.visible()) {
        this.loadNotifications();
      }
    });
    // While open, keep the list live: a new alert, a read on another tab or
    // device, or a reconnect after a drop.
    this.notificationService.changed$.pipe(takeUntilDestroyed()).subscribe(() => {
      if (this.visible()) this.loadNotifications();
    });
  }

  loadNotifications() {
    this.notificationService.list(0, 20).subscribe({
      next: (res) => {
        this.notifications.set(res.items);
      },
      // GET, user-initiated by opening the drawer — not covered by the
      // global error-toast interceptor (mutating methods only), and this
      // is a real user action that deserves feedback, unlike the bell's
      // own silent background poll.
      error: (err) => this.notify.error(errorMessageFor(err)),
    });
  }

  markAsRead(id: string) {
    this.markLocallyRead(id);
    this.notificationService.markRead(id).subscribe();
  }

  markAllAsRead() {
    this.notificationService.markAllRead().subscribe({
      next: () => this.notifications.update((items) => items.map((n) => ({ ...n, is_read: true }))),
    });
  }

  /** Click a notification: mark it read, then jump to what it references. */
  open(notification: NotificationResponse) {
    const link = this.notificationService.routeFor(notification);
    if (!notification.is_read) {
      this.markLocallyRead(notification.id);
      this.notificationService.markRead(notification.id).subscribe();
    }
    if (link) {
      this.visible.set(false);
      void this.router.navigate(link.commands, { queryParams: link.queryParams });
    }
  }

  private markLocallyRead(id: string) {
    this.notifications.update((items) =>
      items.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    );
  }

  onHide() {
    this.visible.set(false);
  }
}
