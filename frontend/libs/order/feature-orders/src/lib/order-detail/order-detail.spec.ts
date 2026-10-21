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
