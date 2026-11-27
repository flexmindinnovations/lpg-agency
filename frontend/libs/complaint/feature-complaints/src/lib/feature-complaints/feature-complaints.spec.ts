import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureComplaints } from './feature-complaints';

describe('FeatureComplaints', () => {
  let component: FeatureComplaints;
  let fixture: ComponentFixture<FeatureComplaints>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureComplaints],
      providers: [
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
        // NotifyService toasts through the app-wide MessageService.
        MessageService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureComplaints);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('picks the customer with the same searchable dropdown as New Booking', () => {
    const form = component as unknown as {
      searchCustomers: (query: string) => import('rxjs').Observable<{ id: string }[]>;
      customerName: (customer: { full_name: string }) => string;
    };
    const http = TestBed.inject(HttpTestingController);
    let found: { id: string }[] = [];

    form.searchCustomers('ravi').subscribe((items) => (found = items));
    const request = http.expectOne((req) => /\/api\/v1\/customers(\?|$)/.test(req.url));
    request.flush({ items: [{ id: 'c1' }], total: 1 });

    expect(request.request.urlWithParams).toContain('search=ravi');
    expect(found).toEqual([{ id: 'c1' }]);
    expect(form.customerName({ full_name: 'Ravi Kumar' })).toBe('Ravi Kumar');
  });
});
