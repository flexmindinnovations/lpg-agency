import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiConfiguration } from '../generated/api-configuration';
import { Subject } from 'rxjs';
import { WebSocketService } from '../websocket.service';
import { NotificationService, groupNotificationsByDay } from './notification';

class FakeWs {
  readonly intents: string[] = [];
  readonly messages$ = new Subject<Record<string, unknown>>();
  readonly reconnected$ = new Subject<void>();
  subscribeTo(intent: string): void {
    this.intents.push(intent);
  }
}
import type { NotificationResponse } from '../generated/models/notification-response';

const notification = (over: Partial<NotificationResponse> = {}): NotificationResponse => ({
  id: 'n1',
  tenant_id: 't1',
  notification_type: 'order_placed_staff',
  title: 'New Order',
  body: 'Order #ABC placed',
  is_read: false,
  created_at: '2026-08-31T00:00:00Z',
  ...over,
});

describe('NotificationService', () => {
  let service: NotificationService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: WebSocketService, useClass: FakeWs },
      ],
    });
    service = TestBed.inject(NotificationService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  describe('unreadCount', () => {
    it('starts at 0 and follows refreshUnreadCount', () => {
      expect(service.unreadCount()).toBe(0);
      service.refreshUnreadCount();
      http.expectOne((r) => r.url.includes('/notifications/unread-count')).flush({ count: 4 });
      expect(service.unreadCount()).toBe(4);
    });

    it('markRead decrements it optimistically then reconciles', () => {
      service.refreshUnreadCount();
      http.expectOne((r) => r.url.includes('/unread-count')).flush({ count: 3 });

      service.markRead('n1').subscribe();
      const patch = http.expectOne((r) => r.method === 'PATCH');
      patch.flush(null);
      // Optimistic drop is visible before the reconcile GET resolves.
      expect(service.unreadCount()).toBe(2);

      http.expectOne((r) => r.url.includes('/unread-count')).flush({ count: 2 });
      expect(service.unreadCount()).toBe(2);
    });

    it('markAllRead zeroes it', () => {
      service.adjustUnreadCount(5);
      service.markAllRead().subscribe();
      http.expectOne((r) => r.method === 'POST').flush(null);
      expect(service.unreadCount()).toBe(5 - 5);
    });

    it('never goes below zero', () => {
      service.markRead('n1').subscribe();
      http.expectOne((r) => r.method === 'PATCH').flush(null);
      http.expectOne((r) => r.url.includes('/unread-count')).flush({ count: 0 });
      expect(service.unreadCount()).toBe(0);
    });
  });

  describe('routeFor', () => {
    it('maps an order reference to the order detail route', () => {
      expect(
        service.routeFor(notification({ reference_type: 'order', reference_id: 'o9' })),
      ).toEqual({ commands: ['/orders', 'o9'] });
    });

    it('deep-links a complaint and sends route alerts to dispatch', () => {
      expect(
        service.routeFor(notification({ reference_type: 'complaint', reference_id: 'c1' })),
      ).toEqual({ commands: ['/complaints'], queryParams: { complaint: 'c1' } });
      expect(
        service.routeFor(notification({ reference_type: 'route', reference_id: 'r1' })),
      ).toEqual({ commands: ['/dispatch'] });
      expect(service.routeFor(notification({ reference_type: 'invoice' }))).toEqual({
        commands: ['/invoices'],
      });
      expect(service.routeFor(notification({ reference_type: 'inventory_location' }))).toEqual({
        commands: ['/inventory'],
      });
    });

    it('returns null when there is nothing to open', () => {
      expect(service.routeFor(notification({ reference_type: null }))).toBeNull();
      expect(service.routeFor(notification({ reference_type: 'mystery' }))).toBeNull();
    });
  });

  describe('realtime', () => {
    it('bumps the badge on a new notification and re-syncs on reads elsewhere', () => {
      const ws = TestBed.inject(WebSocketService) as unknown as FakeWs;
      const changed = jest.fn();
      const arrived = jest.fn();
      jest.useFakeTimers();
      service.changed$.subscribe(changed);
      service.arrived$.subscribe(arrived);
      service.startRealtime();
      service.startRealtime(); // idempotent
      expect(ws.intents).toEqual(['notifications']);

      ws.messages$.next({ type: 'notification.new', notification_id: 'n9', body: 'Hi' });
      expect(service.unreadCount()).toBe(1);
      expect(arrived).toHaveBeenCalledWith(expect.objectContaining({ notification_id: 'n9' }));

      ws.messages$.next({ type: 'notification.read_all' });
      http.expectOne('http://test/api/v1/notifications/unread-count').flush({ count: 0 });
      expect(service.unreadCount()).toBe(0);

      ws.reconnected$.next();
      http.expectOne('http://test/api/v1/notifications/unread-count').flush({ count: 4 });
      expect(service.unreadCount()).toBe(4);

      jest.advanceTimersByTime(200);
      expect(changed).toHaveBeenCalled();
      jest.useRealTimers();
    });
  });
});

describe('groupNotificationsByDay', () => {
  const at = (iso: string): NotificationResponse => notification({ id: iso, created_at: iso });

  it('labels today and yesterday and keeps newest-first order', () => {
    const now = new Date(2026, 9, 20, 15, 0);
    const groups = groupNotificationsByDay(
      [
        at(new Date(2026, 9, 20, 14, 0).toISOString()),
        at(new Date(2026, 9, 20, 9, 0).toISOString()),
        at(new Date(2026, 9, 19, 18, 0).toISOString()),
        at(new Date(2026, 9, 12, 8, 0).toISOString()),
      ],
      now,
    );
    expect(groups.map((g) => g.label.length > 0)).toEqual([true, true, true]);
    expect(groups[0].label).toBe('Today');
    expect(groups[0].items).toHaveLength(2);
    expect(groups[1].label).toBe('Yesterday');
    expect(groups[2].label).not.toMatch(/Today|Yesterday/);
  });

  it('is empty for no notifications', () => {
    expect(groupNotificationsByDay([])).toEqual([]);
  });
});
