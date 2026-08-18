import { HeaderPortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal, forwardRef } from '@angular/core';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { ButtonModule } from 'primeng/button';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';
import { MessageService } from 'primeng/api';
import { NotificationService } from '@lpg/shared/data-access';
import type { NotificationResponse } from '@lpg/shared/data-access';

@Component({
  selector: 'lib-notification-action-cell',
  standalone: true,
  imports: [ButtonModule],
  template: `
    <div class="flex items-center h-full">
      @if (!row?.is_read) {
      <p-button
        icon="pi pi-check"
        [text]="true"
        [rounded]="true"
        severity="secondary"
        size="small"
        (onClick)="handleClick()">
      </p-button>
      }
    </div>
  `
})
export class NotificationActionCell {
  private readonly notificationService = inject(NotificationService);
  private readonly parent = inject(forwardRef(() => NotificationFeatureNotifications));
  row: NotificationResponse | undefined;

  agInit(params: any): void {
    this.row = params.data;
  }
  
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }

  handleClick(): void {
    if (this.row) {
      this.notificationService.markRead(this.row.id).subscribe(() => {
        this.parent.loadNotifications();
      });
    }
  }
}

@Component({
  selector: 'lib-notification-feature-notifications',
  imports: [HeaderPortalDirective, ButtonDirective, ButtonIcon, ButtonLabel, DataGridComponent],
  templateUrl: './notification-feature-notifications.html',
  styleUrl: './notification-feature-notifications.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class NotificationFeatureNotifications implements OnInit {
  private readonly notificationService = inject(NotificationService);
  private readonly messageService = inject(MessageService);

  protected readonly notifications = signal<NotificationResponse[]>([]);
  protected readonly loading = signal(false);

  protected readonly columns: DataGridColumn<NotificationResponse>[] = [
    { field: 'title', header: 'Title', sortable: true, flex: 2 },
    { field: 'body', header: 'Message', sortable: true, flex: 3 },
    { 
      field: 'is_read', 
      header: 'Status', 
      sortable: true,
      valueFormatter: (value: unknown) => value ? 'Read' : 'Unread'
    },
    { 
      field: 'created_at', 
      header: 'Date', 
      sortable: true,
      valueFormatter: (value: unknown) => new Date(value as string).toLocaleString()
    },
    {
      field: 'id',
      header: 'Actions',
      cellRenderer: NotificationActionCell
    }
  ];

  ngOnInit(): void {
    this.loadNotifications();
  }

  loadNotifications(): void {
    this.loading.set(true);
    this.notificationService.list(0, 100).subscribe({
      next: (res) => {
        this.notifications.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load notifications' });
      }
    });
  }

  markAsRead(id: string): void {
    this.loading.set(true);
    this.notificationService.markRead(id).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Notification marked as read' });
        this.loadNotifications();
      },
      error: () => {
        this.loading.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to mark as read' });
      }
    });
  }

  markAllAsRead(): void {
    this.loading.set(true);
    this.notificationService.markAllRead().subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'All notifications marked as read' });
        this.loadNotifications();
      },
      error: () => {
        this.loading.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to mark all as read' });
      }
    });
  }
}
