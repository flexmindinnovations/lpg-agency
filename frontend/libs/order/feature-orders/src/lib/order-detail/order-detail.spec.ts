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

  describe('Amount', () => {
    const order = (extra: Record<string, unknown>) => ({
      id: 'order-1',
      order_number: 'ORD000063',
      branch_id: 'branch-1',
      status: 'confirmed',
      booking_source: 'staff',
      requested_date: '2026-10-30T00:00:00Z',
      delivery_address: { address_line: 'Somewhere' },
      lines: [],
      ...extra,
    });

    it('shows the price, the GST and the total to pay once GST is worked out', () => {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      TestBed.inject(HttpTestingController)
        .expectOne('http://test/api/v1/orders/order-1')
        .flush(order({ total_amount: '905.50', tax_amount: '45.28', payable_amount: '950.78' }));
      fixture.detectChanges();
      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('Price before GST');
      expect(text).toContain('Total to pay');
      expect(text).toContain('950.78');
      expect(text).toContain('45.28');
    });

    it('keeps "+ GST" for an order priced before GST was recorded', () => {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      TestBed.inject(HttpTestingController)
        .expectOne('http://test/api/v1/orders/order-1')
        .flush(order({ total_amount: '905.50' }));
      fixture.detectChanges();
      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('+ GST');
      expect(text).not.toContain('Total to pay');
    });

    const bookedLine = {
      id: 'line-1',
      cylinder_type_id: 'type-1',
      quantity_ordered: 1,
      quantity_delivered: 0,
      quantity_pending: 0,
      quantity_collected_empty: 0,
      is_backordered: false,
      unit_price: null,
    };

    function show(extra: Record<string, unknown>): string {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      TestBed.inject(HttpTestingController)
        .expectOne('http://test/api/v1/orders/order-1')
        .flush(order({ status: 'booked', total_amount: null, lines: [bookedLine], ...extra }));
      fixture.detectChanges();
      return (fixture.nativeElement as HTMLElement).textContent ?? '';
    }

    it('shows what a booked order would cost, marked as an estimate', () => {
      const text = show({
        price_estimate: {
          lines: [{ line_id: 'line-1', unit_price: '2100.00' }],
          total_amount: '2100.00',
          tax_amount: '378.00',
          payable_amount: '2478.00',
          prices_include_gst: false,
        },
      });

      expect(text).toContain('Price before GST');
      expect(text).toContain('Estimated total to pay');
      expect(text).toContain('2,478.00');
      expect(text).toContain('378.00');
      expect(text).toContain('2,100.00');
      expect(text).toContain('estimate');
      expect(text).toContain('fixed when the order is confirmed');
      expect(text).not.toContain('Not confirmed yet');
    });

    it('says the price includes GST when the agency prices that way', () => {
      const text = show({
        price_estimate: {
          lines: [{ line_id: 'line-1', unit_price: '2100.00' }],
          total_amount: '2100.00',
          tax_amount: '320.34',
          payable_amount: '2100.00',
          prices_include_gst: true,
        },
      });

      expect(text).toContain('Price including GST');
      expect(text).not.toContain('Price before GST');
    });

    it('shows the price alone while a GST rate is missing', () => {
      const text = show({
        price_estimate: {
          lines: [{ line_id: 'line-1', unit_price: '2100.00' }],
          total_amount: '2100.00',
          tax_amount: null,
          payable_amount: null,
          prices_include_gst: null,
        },
      });

      expect(text).toContain('Estimated price');
      expect(text).toContain('set the GST rate under Cylinders & Prices');
      expect(text).not.toContain('Estimated total to pay');
    });

    it('shows Backordered as a chip', () => {
      const fixture = TestBed.createComponent(OrderDetail);
      fixture.detectChanges();
      TestBed.inject(HttpTestingController)
        .expectOne('http://test/api/v1/orders/order-1')
        .flush(order({ lines: [{ ...bookedLine, is_backordered: true }] }));
      fixture.detectChanges();
      const chips = Array.from(
        (fixture.nativeElement as HTMLElement).querySelectorAll('td .p-tag-warn'),
      );

      expect(chips.map((chip) => chip.textContent?.trim())).toEqual(['Yes']);
    });

    it('keeps "Not confirmed yet" when there is no estimate', () => {
      const text = show({ price_estimate: null });

      expect(text).toContain('Not confirmed yet');
      expect(text).not.toContain('estimate');
    });

    it('lists the empties collected of sizes that are not on the order', () => {
      const text = show({
        status: 'delivered',
        other_empties: [{ cylinder_type_id: 'type-5kg', quantity: 3 }],
      }).replace(/\s+/g, ' ');
      expect(text).toContain('type-5kg not on this order———3——');
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
