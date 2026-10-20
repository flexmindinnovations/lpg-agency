import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { Validators } from '@angular/forms';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { OrderQueue } from './order-queue';

describe('OrderQueue', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrderQueue],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        {
          provide: ActivatedRoute,
          useValue: { queryParamMap: of(convertToParamMap({})) },
        },
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(OrderQueue);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });

  describe('booking source', () => {
    type Internals = {
      bookingSourceOptions: { value: string; label: string }[];
      createForm: { controls: { booking_source: import('@angular/forms').FormControl<string> } };
      orderColumns: { field: string; cellRendererParams?: Record<string, unknown> }[];
    };
    const internals = () =>
      TestBed.createComponent(OrderQueue).componentInstance as unknown as Internals;

    it('offers staff the dashboard and the channels a customer may have used, never the app', () => {
      const options = internals().bookingSourceOptions;

      expect(options.map((o) => o.value)).toEqual(['staff', 'phone', 'walk_in', 'whatsapp']);
      expect(options[0].label).toBe('Dashboard');
    });

    it('defaults to the dashboard and does not make staff choose one', () => {
      const control = internals().createForm.controls.booking_source;

      expect(control.value).toBe('staff');
      expect(control.hasValidator(Validators.required)).toBe(false);
    });

    it('labels the Source column with the shared names and marks the app orders', () => {
      const column = internals().orderColumns.find((c) => c.field === 'booking_source');

      expect(column?.cellRendererParams?.['labelMap']).toMatchObject({
        staff: 'Dashboard',
        mobile_app: 'Mobile app',
      });
      expect(column?.cellRendererParams?.['severityMap']).toEqual({ mobile_app: 'info' });
    });
  });

  describe('cylinder choices', () => {
    type Internals = {
      createForm: { controls: { customer: import('@angular/forms').FormControl<unknown> } };
      cylinderTypeOptions: () => { value: string; label: string }[];
      availableFor: (id: string) => number | null;
    };

    it('offers only what the selected customer can order, with price and stock', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as Internals;
      const http = TestBed.inject(HttpTestingController);

      component.createForm.controls.customer.setValue({ id: 'cust-1', addresses: [] });
      const request = http.expectOne(
        (req) =>
          req.url === 'http://test/api/v1/orders/orderable-cylinder-types' &&
          req.params.get('customer_id') === 'cust-1',
      );
      request.flush([
        {
          cylinder_type_id: 'ct-1',
          name: 'Domestic 14.2kg',
          weight_kg: '14.2',
          unit_price: '903.00',
          available_quantity: 12,
        },
      ]);

      expect(component.cylinderTypeOptions()).toEqual([
        { value: 'ct-1', label: 'Domestic 14.2kg · ₹903.00 · 12 in stock' },
      ]);
      expect(component.availableFor('ct-1')).toBe(12);

      component.createForm.controls.customer.setValue(null);
      expect(component.cylinderTypeOptions()).toEqual([]);
    });

    it('asks for nothing while a customer is still being typed', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as Internals;
      const http = TestBed.inject(HttpTestingController);

      component.createForm.controls.customer.setValue('Meen');

      http.expectNone((req) => req.url.endsWith('/orders/orderable-cylinder-types'));
    });

    it('picks the primary address so a booking needs no extra step', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as Internals & {
        createForm: { controls: { address_id: import('@angular/forms').FormControl<string> } };
      };

      component.createForm.controls.customer.setValue({
        id: 'cust-2',
        addresses: [
          { id: 'a-1', is_primary: false, line_1: 'Office' },
          { id: 'a-2', is_primary: true, line_1: 'Home' },
        ],
      });

      expect(component.createForm.controls.address_id.value).toBe('a-2');
    });
  });

  describe('order list', () => {
    it('searches by order number, customer or phone, with whitespace collapsed', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as {
        loadOrders: () => void;
        searchText: { set: (v: string) => void };
      };
      const http = TestBed.inject(HttpTestingController);

      component.searchText.set('  meena   iyer ');
      component.loadOrders();

      const request = http.expectOne(
        (req) =>
          req.url === 'http://test/api/v1/orders' && req.params.get('search') === 'meena iyer',
      );
      request.flush({ items: [], total: 0 });
    });

    it('shows the customer on every row', () => {
      const component = TestBed.createComponent(OrderQueue).componentInstance as unknown as {
        orderColumns: { header: string }[];
      };
      expect(component.orderColumns.map((c) => c.header)).toEqual(
        expect.arrayContaining(['Customer', 'Phone', 'Consumer no.']),
      );
    });
  });
});
