import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { ApiConfiguration, type InvoiceResponse } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureInvoices } from './feature-invoices';

const INVOICE: InvoiceResponse = {
  invoice_id: 'inv-1',
  invoice_number: 'INV-2026-000001',
  tenant_id: 't',
  customer_id: 'c',
  customer_name: 'Asha Rao',
  order_id: 'o',
  order_number: 'ORD-1',
  status: 'issued',
  subtotal: '900.00',
  tax_amount: '45.00',
  total_amount: '945.00',
  amount_paid: '0.00',
  balance_due: '945.00',
  issued_at: '2026-10-01T10:00:00Z',
  lines: [],
  payments: [],
  version: 1,
};

describe('FeatureInvoices', () => {
  let component: FeatureInvoices;
  let fixture: ComponentFixture<FeatureInvoices>;
  let http: HttpTestingController;

  beforeEach(async () => {
    const permissions = new Set(['invoices:read', 'invoices:record_payment', 'invoices:issue']);
    await TestBed.configureTestingModule({
      imports: [FeatureInvoices],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: PERMISSION_CHECKER, useValue: signal({ permissions }) },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureInvoices);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('loads a server page with filters and the invoices on hold', () => {
    const list = http.expectOne((req) => req.url.endsWith('/api/v1/invoices'));
    expect(list.request.params.get('page')).toBe('1');
    expect(list.request.params.get('page_size')).toBe('25');
    list.flush({ items: [INVOICE], total: 1, page: 1, page_size: 25 });
    http.expectOne((req) => req.url.endsWith('/api/v1/invoices/uninvoiced-orders')).flush([]);
    expect(component.invoices()).toEqual([INVOICE]);
  });

  it('requires a reference for a cheque payment', () => {
    component.onInvoiceSelected(INVOICE);
    component.openPaymentDrawer();
    const form = component.paymentForm;
    expect(form.controls.amount.value).toBe('945.00');
    form.controls.method.setValue('cheque');
    expect(form.controls.reference.hasError('required')).toBe(true);
    form.controls.reference.setValue('000451');
    expect(form.valid).toBe(true);
  });
});
