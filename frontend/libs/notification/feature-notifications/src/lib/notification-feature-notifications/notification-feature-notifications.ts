import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { SelectButton } from 'primeng/selectbutton';
import { FormsModule } from '@angular/forms';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { EmptyStateComponent, SkeletonComponent } from '@lpg/shared/ui';
import {
  NotificationService,
  NotifyService,
  groupNotificationsByDay,
} from '@lpg/shared/data-access';
import type { NotificationResponse } from '@lpg/shared/data-access';

type InboxFilter = 'all' | 'unread';

/**
 * The full inbox: newest first, grouped by day, unread ones marked, each
 * opening the order / complaint / trip it is about. Stays live — new
 * alerts and reads on other tabs or devices reload it (`changed$`).
 */
@Component({
  selector: 'lib-notification-feature-notifications',
  imports: [
    DatePipe,
    FormsModule,
    HeaderTitlePortalDirective,
    ButtonDirective,
    SelectButton,
    EmptyStateComponent,
    SkeletonComponent,
  ],
  templateUrl: './notification-feature-notifications.html',
  styleUrl: './notification-feature-notifications.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotificationFeatureNotifications implements OnInit {
  private readonly notificationService = inject(NotificationService);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);

  protected readonly notifications = signal<NotificationResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly loaded = signal(false);
  protected readonly filter = signal<InboxFilter>('all');
  protected readonly filterOptions = [
    { label: 'All', value: 'all' },
    { label: 'Unread', value: 'unread' },
  ];

  protected readonly unreadCount = this.notificationService.unreadCount;
  protected readonly groups = computed(() => {
    const items =
      this.filter() === 'unread'
        ? this.notifications().filter((n) => !n.is_read)
        : this.notifications();
    return groupNotificationsByDay(items);
  });

  constructor() {
    this.notificationService.changed$
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.loadNotifications({ silent: true }));
  }

  ngOnInit(): void {
    this.loadNotifications();
    // Keep the shared bell badge in sync with what this page shows.
    this.notificationService.refreshUnreadCount();
  }

  protected hasLink(notification: NotificationResponse): boolean {
    return this.notificationService.routeFor(notification) !== null;
  }

  protected setFilter(value: InboxFilter | null): void {
    this.filter.set(value ?? 'all');
  }

  /** Mark a notification read and navigate to what it references. */
  open(notification: NotificationResponse): void {
    const link = this.notificationService.routeFor(notification);
    if (!notification.is_read) this.markAsRead(notification.id);
    if (link) {
      void this.router.navigate(link.commands, { queryParams: link.queryParams });
    }
  }

  loadNotifications(options: { silent?: boolean } = {}): void {
    if (!options.silent) this.loading.set(true);
    this.notificationService.list(0, 100).subscribe({
      next: (res) => {
        this.notifications.set(res.items);
        this.loading.set(false);
        this.loaded.set(true);
      },
      // GET — not covered by the global error-toast interceptor
      // (mutating methods only).
      error: () => {
        this.loading.set(false);
        this.loaded.set(true);
        if (!options.silent) this.notify.error('Failed to load notifications');
      },
    });
  }

  markAsRead(id: string): void {
    // Optimistic — the row loses its unread styling at once.
    this.notifications.update((items) =>
      items.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    );
    this.notificationService.markRead(id).subscribe({
      error: () => this.loadNotifications({ silent: true }),
    });
  }

  markAllAsRead(): void {
    this.notificationService.markAllRead().subscribe({
      next: () => {
        this.notifications.update((items) => items.map((n) => ({ ...n, is_read: true })));
        this.notify.success('All notifications marked as read');
      },
    });
  }
}
