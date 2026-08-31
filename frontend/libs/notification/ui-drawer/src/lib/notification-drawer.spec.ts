import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { ApiConfiguration, NotificationService } from '@lpg/shared/data-access';
import { NotificationDrawer } from './notification-drawer';

describe('NotificationDrawer', () => {
  let component: NotificationDrawer;
  let fixture: ComponentFixture<NotificationDrawer>;
  let list: jest.Mock;

  beforeEach(async () => {
    list = jest.fn().mockReturnValue(
      of({
        items: [
          {
            id: 'n1',
            tenant_id: 't1',
            notification_type: 'order_placed_staff',
            title: 'New Order',
            body: 'Order #ABC was just placed.',
            is_read: false,
            created_at: '2026-08-31T00:00:00Z',
          },
        ],
      }),
    );

    await TestBed.configureTestingModule({
      imports: [NotificationDrawer],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: NotificationService, useValue: { list } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationDrawer);
    component = fixture.componentInstance;
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
});
