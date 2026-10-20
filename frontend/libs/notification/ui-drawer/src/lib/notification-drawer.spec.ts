import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject, of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { ApiConfiguration, NotificationService } from '@lpg/shared/data-access';
import { NotificationDrawer } from './notification-drawer';

const item = (over: Record<string, unknown> = {}) => ({
  id: 'n1',
  tenant_id: 't1',
  notification_type: 'order_placed_staff',
  title: 'New Order',
  body: 'Order #ABC was just placed.',
  is_read: false,
  created_at: '2026-08-31T00:00:00Z',
  reference_type: 'order',
  reference_id: 'o9',
  ...over,
});

describe('NotificationDrawer', () => {
  let component: NotificationDrawer;
  let fixture: ComponentFixture<NotificationDrawer>;
  let list: jest.Mock;
  let markRead: jest.Mock;
  let markAllRead: jest.Mock;
  let changed: Subject<void>;
  let navigate: jest.SpyInstance;

  beforeEach(async () => {
    list = jest.fn().mockReturnValue(of({ items: [item()] }));
    markRead = jest.fn().mockReturnValue(of(undefined));
    markAllRead = jest.fn().mockReturnValue(of(undefined));
    changed = new Subject<void>();

    await TestBed.configureTestingModule({
      imports: [NotificationDrawer],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        MessageService,
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        {
          provide: NotificationService,
          useValue: {
            list,
            markRead,
            markAllRead,
            changed$: changed,
            routeFor: (n: { reference_type?: string; reference_id?: string }) =>
              n.reference_type === 'order' && n.reference_id
                ? { commands: ['/orders', n.reference_id] }
                : n.reference_type === 'complaint' && n.reference_id
                  ? { commands: ['/complaints'], queryParams: { complaint: n.reference_id } }
                  : null,
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationDrawer);
    component = fixture.componentInstance;
    navigate = jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('does not fetch while closed', () => {
    expect(list).not.toHaveBeenCalled();
  });

  it('fetches notifications every time it is opened', async () => {
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(list).toHaveBeenCalledTimes(1);
    expect(component.notifications()).toHaveLength(1);

    // Close then reopen — must refetch, not show stale data.
    component.visible.set(false);
    fixture.detectChanges();
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('open() marks an unread notification read and navigates to its reference', () => {
    component.open(item() as never);

    expect(markRead).toHaveBeenCalledWith('n1');
    expect(navigate).toHaveBeenCalledWith(['/orders', 'o9'], { queryParams: undefined });
    expect(component.visible()).toBe(false);
  });

  it('open() does not re-mark an already-read notification', () => {
    component.open(item({ is_read: true }) as never);

    expect(markRead).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/orders', 'o9'], { queryParams: undefined });
  });

  it('open() on a notification with no linkable reference just marks it read', () => {
    component.open(item({ reference_type: null, reference_id: null }) as never);

    expect(markRead).toHaveBeenCalledWith('n1');
    expect(navigate).not.toHaveBeenCalled();
  });

  it('clearAll() hides every notification from the drawer without touching the server', async () => {
    list.mockReturnValue(of({ items: [item({ id: 'a' }), item({ id: 'b' })] }));
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.visibleNotifications()).toHaveLength(2);

    component.clearAll();

    expect(component.visibleNotifications()).toHaveLength(0);
    // The raw list is untouched; nothing was marked read on the server.
    expect(component.notifications()).toHaveLength(2);
    expect(markRead).not.toHaveBeenCalled();
  });

  it('a genuinely new notification still shows after clearAll()', async () => {
    list.mockReturnValue(of({ items: [item({ id: 'a' })] }));
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    component.clearAll();
    expect(component.visibleNotifications()).toHaveLength(0);

    list.mockReturnValue(of({ items: [item({ id: 'a' }), item({ id: 'new' })] }));
    component.loadNotifications();
    expect(component.visibleNotifications().map((n) => n.id)).toEqual(['new']);
  });

  it('open() deep-links a complaint and shows it read straight away', async () => {
    list.mockReturnValue(
      of({ items: [item({ reference_type: 'complaint', reference_id: 'c1' })] }),
    );
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();

    component.open(component.notifications()[0]);

    expect(navigate).toHaveBeenCalledWith(['/complaints'], { queryParams: { complaint: 'c1' } });
    expect(component.notifications()[0].is_read).toBe(true);
  });

  it('groups by day and reloads live while open', async () => {
    const today = new Date().toISOString();
    list.mockReturnValue(of({ items: [item({ id: 'a', created_at: today })] }));
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.groups().map((g) => g.label)).toEqual(['Today']);

    changed.next();
    expect(list).toHaveBeenCalledTimes(2);

    component.visible.set(false);
    changed.next();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('markAllAsRead() clears every unread marker', async () => {
    list.mockReturnValue(of({ items: [item({ id: 'a' }), item({ id: 'b' })] }));
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.hasUnread()).toBe(true);

    component.markAllAsRead();

    expect(markAllRead).toHaveBeenCalled();
    expect(component.hasUnread()).toBe(false);
  });

  it('shows a friendly empty state', async () => {
    list.mockReturnValue(of({ items: [] }));
    component.visible.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(document.body.textContent).toContain("You're all caught up");
  });
});
