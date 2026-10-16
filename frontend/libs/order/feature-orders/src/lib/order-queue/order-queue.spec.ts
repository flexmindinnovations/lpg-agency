import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { Validators } from '@angular/forms';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
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
});
