import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';
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
  let navigate: jest.SpyInstance;

  beforeEach(async () => {
    list = jest.fn().mockReturnValue(of({ items: [item()] }));
    markRead = jest.fn().mockReturnValue(of(undefined));

    await TestBed.configureTestingModule({
      imports: [NotificationDrawer],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        {
          provide: NotificationService,
          useValue: {
            list,
            markRead,
            routeFor: (n: { reference_type?: string; reference_id?: string }) =>
              n.reference_type === 'order' && n.reference_id
                ? ['/orders', n.reference_id]
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
    expect(navigate).toHaveBeenCalledWith(['/orders', 'o9']);
    expect(component.visible()).toBe(false);
  });

  it('open() does not re-mark an already-read notification', () => {
    component.open(item({ is_read: true }) as never);

    expect(markRead).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/orders', 'o9']);
  });

  it('open() on a notification with no linkable reference just marks it read', () => {
    component.open(item({ reference_type: null, reference_id: null }) as never);

    expect(markRead).toHaveBeenCalledWith('n1');
    expect(navigate).not.toHaveBeenCalled();
  });
});
