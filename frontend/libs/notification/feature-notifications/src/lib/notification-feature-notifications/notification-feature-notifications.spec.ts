import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { Subject, of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { NotificationService } from '@lpg/shared/data-access';
import { NotificationFeatureNotifications } from './notification-feature-notifications';

const item = (over: Record<string, unknown> = {}) => ({
  id: 'n1',
  tenant_id: 't1',
  notification_type: 'cancellation_requested_staff',
  title: 'Cancellation waiting for approval',
  body: 'ORD000009 for Meena Iyer: cancellation requested — approve or decline it.',
  is_read: false,
  created_at: new Date().toISOString(),
  reference_type: 'order',
  reference_id: 'o9',
  ...over,
});

describe('NotificationFeatureNotifications', () => {
  let component: NotificationFeatureNotifications;
  let fixture: ComponentFixture<NotificationFeatureNotifications>;
  let list: jest.Mock;
  let markRead: jest.Mock;
  let changed: Subject<void>;

  beforeEach(async () => {
    list = jest.fn().mockReturnValue(of({ items: [item(), item({ id: 'n2', is_read: true })] }));
    markRead = jest.fn().mockReturnValue(of(undefined));
    changed = new Subject<void>();

    await TestBed.configureTestingModule({
      imports: [NotificationFeatureNotifications],
      providers: [
        provideRouter([]),
        MessageService,
        {
          provide: NotificationService,
          useValue: {
            list,
            markRead,
            markAllRead: jest.fn().mockReturnValue(of(undefined)),
            refreshUnreadCount: jest.fn(),
            unreadCount: signal(1),
            changed$: changed,
            routeFor: (n: { reference_type?: string; reference_id?: string }) =>
              n.reference_type === 'order' ? { commands: ['/orders', n.reference_id] } : null,
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationFeatureNotifications);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('lists notifications grouped by day with unread ones marked', () => {
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('.inbox__day-label')?.textContent).toContain('Today');
    expect(el.querySelectorAll('.inbox__item')).toHaveLength(2);
    expect(el.querySelectorAll('.inbox__item--unread')).toHaveLength(1);
    expect(el.textContent).toContain('ORD000009 for Meena Iyer');
  });

  it('opening one marks it read and goes to the order', () => {
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('.inbox__open')
      ?.click();
    expect(markRead).toHaveBeenCalledWith('n1');
    expect(navigate).toHaveBeenCalledWith(['/orders', 'o9'], { queryParams: undefined });
  });

  it('reloads when notifications change elsewhere', () => {
    changed.next();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('shows an empty state', async () => {
    list.mockReturnValue(of({ items: [] }));
    component.loadNotifications();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No notifications yet');
  });
});
