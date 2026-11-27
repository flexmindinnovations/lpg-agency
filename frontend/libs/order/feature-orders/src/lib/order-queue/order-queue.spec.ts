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

    const isRequestFor =
      (list: 'orderable' | 'unorderable', customerId: string) =>
      (req: { url: string; params: { get: (name: string) => string | null } }) =>
        req.url === `http://test/api/v1/orders/${list}-cylinder-types` &&
        req.params.get('customer_id') === customerId;

    const option = {
      cylinder_type_id: 'ct-1',
      name: 'Domestic 14.2kg',
      weight_kg: '14.2',
      unit_price: '903.00',
      available_quantity: 12,
    };
    const unpriced = {
      cylinder_type_id: 'ct-2',
      name: 'Commercial 19kg',
      reasons: ['No price for domestic customers at this branch', 'No free filled stock'],
    };

    /** Picks a customer in the open form and answers the booking list. */
    function pickCustomer(orderable: object[]) {
      const fixture = TestBed.createComponent(OrderQueue);
      const http = TestBed.inject(HttpTestingController);
      const component = fixture.componentInstance as unknown as Internals & {
        showCreateDrawer: { set: (open: boolean) => void };
      };
      component.showCreateDrawer.set(true);
      fixture.detectChanges();
      component.createForm.controls.customer.setValue({ id: 'cust-1', addresses: [] });
      http.expectOne(isRequestFor('orderable', 'cust-1')).flush(orderable);
      const reasons = http.expectOne(isRequestFor('unorderable', 'cust-1'));
      const text = () => {
        fixture.detectChanges();
        return (document.body.textContent ?? '').replace(/\s+/g, ' ');
      };
      return { fixture, reasons, text };
    }

    it('tells staff why nothing can be booked', () => {
      const { fixture, reasons, text } = pickCustomer([]);
      reasons.flush([unpriced]);

      expect(text()).toContain('No cylinder can be booked for this customer right now:');
      expect(text()).toContain(
        'Commercial 19kg: No price for domestic customers at this branch. No free filled stock',
      );
      fixture.destroy();
    });

    it('lists what is missing beside the types that can be booked', () => {
      const { fixture, reasons, text } = pickCustomer([option]);
      reasons.flush([unpriced]);

      expect(text()).toContain('Not available for this customer:');
      expect(text()).toContain('Commercial 19kg: No price for domestic customers');
      expect(text()).not.toContain('No cylinder can be booked');
      fixture.destroy();
    });

    it('says when there is no active cylinder type at all', () => {
      const { fixture, reasons, text } = pickCustomer([]);
      reasons.flush([]);

      expect(text()).toContain('There is no active cylinder type.');
      fixture.destroy();
    });

    it('keeps the general message when the reasons fail to load', () => {
      const { fixture, reasons, text } = pickCustomer([]);
      reasons.flush(null, { status: 500, statusText: 'Server Error' });

      expect(text()).toContain('A cylinder shows here only when it is active');
      fixture.destroy();
    });

    it('offers only what the selected customer can order, with price and stock', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as Internals;
      const http = TestBed.inject(HttpTestingController);

      component.createForm.controls.customer.setValue({ id: 'cust-1', addresses: [] });
      http.expectOne(isRequestFor('orderable', 'cust-1')).flush([option]);
      http.expectOne(isRequestFor('unorderable', 'cust-1')).flush([]);

      expect(component.cylinderTypeOptions()).toEqual([
        { value: 'ct-1', label: 'Domestic 14.2kg · ₹903.00 + GST · 12 in stock' },
      ]);
      expect(component.availableFor('ct-1')).toBe(12);

      component.createForm.controls.customer.setValue(null);
      expect(component.cylinderTypeOptions()).toEqual([]);
    });

    it('searches customers on the server, from the first character', () => {
      const fixture = TestBed.createComponent(OrderQueue);
      const component = fixture.componentInstance as unknown as {
        searchCustomers: (query: string) => import('rxjs').Observable<{ id: string }[]>;
      };
      const http = TestBed.inject(HttpTestingController);
      const isList = (url: string) => /\/api\/v1\/customers(\?|$)/.test(url);
      let found: { id: string }[] = [];

      component.searchCustomers('').subscribe();
      const first = http.expectOne((req) => isList(req.url));
      expect(first.request.urlWithParams).not.toContain('search=');
      expect(first.request.urlWithParams).toContain('limit=20');

      component.searchCustomers('m').subscribe((items) => (found = items));
      const typed = http.expectOne((req) => isList(req.url));
      expect(typed.request.urlWithParams).toContain('search=m');
      typed.flush({ items: [{ id: 'cust-1' }], total: 1 });
      expect(found).toEqual([{ id: 'cust-1' }]);
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
