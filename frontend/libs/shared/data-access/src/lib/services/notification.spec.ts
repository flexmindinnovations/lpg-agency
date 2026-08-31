import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiConfiguration } from '../generated/api-configuration';
import { NotificationService } from './notification';
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
      http
        .expectOne((r) => r.url.includes('/notifications/unread-count'))
        .flush({ count: 4 });
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
      ).toEqual(['/orders', 'o9']);
    });

    it('falls back to the list route for invoice / complaint references', () => {
      expect(service.routeFor(notification({ reference_type: 'invoice' }))).toEqual(['/invoices']);
      expect(service.routeFor(notification({ reference_type: 'complaint' }))).toEqual([
        '/complaints',
      ]);
    });

    it('returns null when there is nothing to open', () => {
      expect(service.routeFor(notification({ reference_type: null }))).toBeNull();
      expect(service.routeFor(notification({ reference_type: 'mystery' }))).toBeNull();
    });
  });
});
