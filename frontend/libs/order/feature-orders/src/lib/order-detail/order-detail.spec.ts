import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { OrderDetail } from './order-detail';

describe('OrderDetail', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrderDetail],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        MessageService,
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: PERMISSION_CHECKER, useValue: signal({ permissions: new Set<string>() }) },
        {
          provide: ActivatedRoute,
          useValue: { paramMap: of(convertToParamMap({ id: 'order-1' })) },
        },
      ],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(OrderDetail);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });

  describe('Driver and vehicle', () => {
    it('shows the driver, van and last known position while out for delivery', () => {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      const http = TestBed.inject(HttpTestingController);
      http.expectOne('http://test/api/v1/orders/order-1').flush({
        id: 'order-1',
        order_number: 'ORD000033',
        branch_id: 'branch-1',
        status: 'out_for_delivery',
        route_stop_id: 'stop-1',
        booking_source: 'staff',
        requested_date: '2026-10-29T00:00:00Z',
        delivery_address: { address_line: 'Somewhere' },
        lines: [],
      });
      http.expectOne('http://test/api/v1/orders/order-1/tracking').flush({
        order_id: 'order-1',
        status: 'out_for_delivery',
        destination_latitude: 17.4,
        destination_longitude: 78.4,
        destination_label: 'Somewhere',
        route_status: 'in_progress',
        route_id: 'route-1',
        driver_location: {
          latitude: 17.41,
          longitude: 78.41,
          recorded_at: new Date().toISOString(),
        },
        driver: {
          name: 'Ravi Kumar',
          phone_number: '+919999999999',
          vehicle_number: 'TS09AB1234',
          vehicle_model: null,
        },
      });
      fixture.detectChanges();
      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('Driver and vehicle');
      expect(text).toContain('Ravi Kumar');
      expect(text).toContain('TS09AB1234');
      expect(text).toContain('Updated just now');
      expect(fixture.nativeElement.querySelector('iframe')).not.toBeNull();
    });
  });

  describe('Approve Cancellation', () => {
    const outForDelivery = {
      id: 'order-1',
      order_number: 'ORD000026',
      branch_id: 'branch-1',
      status: 'out_for_delivery',
      route_stop_id: null,
      lines: [],
    };

    function loadWith(pending: unknown) {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      const http = TestBed.inject(HttpTestingController);
      http.expectOne('http://test/api/v1/orders/order-1').flush(outForDelivery);
      http.expectOne('http://test/api/v1/orders/order-1/cancellation-request').flush(pending);
      return fixture.componentInstance;
    }

    it('is hidden when no cancellation request is waiting', () => {
      const component = loadWith(null);
      expect(component['canApproveCancellation']()).toBe(false);
      expect(component['requiresCancelApproval']()).toBe(true);
    });

    it('shows, and Cancel Order hides, when a request is waiting', () => {
      const component = loadWith({
        id: 'cr-1',
        order_id: 'order-1',
        reason: 'Customer not home',
        requested_by: 'user-1',
        requested_at: '2026-10-20T04:00:00Z',
      });
      expect(component['canApproveCancellation']()).toBe(true);
      expect(component['requiresCancelApproval']()).toBe(false);
    });
  });
});
