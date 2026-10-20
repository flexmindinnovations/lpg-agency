import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureComplianceCalendar, daysUntil, expiryUrgency } from './feature-compliance-calendar';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 500 };

function isoInDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

describe('FeatureComplianceCalendar', () => {
  let component: FeatureComplianceCalendar;
  let fixture: ComponentFixture<FeatureComplianceCalendar>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureComplianceCalendar],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureComplianceCalendar);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  /** Answers the requests the page makes on init. */
  function flushInit(options: { warehouses?: unknown[]; upcoming?: unknown[] } = {}): void {
    fixture.detectChanges();
    httpMock.expectOne('http://test/api/v1/admin/warehouses').flush(options.warehouses ?? []);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });
    const upcoming = httpMock.expectOne((r) => r.url === 'http://test/api/v1/compliance-documents');
    expect(upcoming.request.params.get('expiry')).toBe('upcoming');
    upcoming.flush({ items: options.upcoming ?? [], total: options.upcoming?.length ?? 0 });
    httpMock
      .expectOne((r) => r.url === 'http://test/api/v1/drivers')
      .flush({
        ...EMPTY_PAGE,
        items: [{ id: 'd1', name: 'Ravi Kumar', license_number: 'DL-1' }],
      });
    httpMock
      .expectOne((r) => r.url === 'http://test/api/v1/vehicles')
      .flush({
        ...EMPTY_PAGE,
        items: [{ id: 'v1', registration_number: 'MH12AB1234' }],
      });
  }

  it('should create', () => {
    expect(component).toBeTruthy();
    flushInit();
  });

  it('auto-selects the first warehouse and loads its documents on init', () => {
    flushInit({
      warehouses: [
        { id: 'w1', branch_id: 'b1', name: 'Warehouse 1', address_line: 'Line 1' },
        { id: 'w2', branch_id: 'b1', name: 'Warehouse 2', address_line: 'Line 2' },
      ],
    });

    expect(component['selectedWarehouseId']()).toBe('w1');
    httpMock.expectOne('http://test/api/v1/warehouses/w1/documents').flush({ items: [], total: 0 });
  });

  it('lists upcoming expiries across owners with names and urgency', () => {
    const doc = (
      id: string,
      owner_type: string,
      owner_id: string,
      doc_type: string,
      days: number,
    ) => ({
      id,
      owner_type,
      owner_id,
      doc_type,
      document_number: id.toUpperCase(),
      expiry_date: isoInDays(days),
      verification_status: 'verified',
    });
    flushInit({
      warehouses: [{ id: 'w1', branch_id: 'b1', name: 'Main godown', address_line: 'x' }],
      upcoming: [
        doc('a', 'driver', 'd1', 'driving_licence', -2),
        doc('b', 'vehicle', 'v1', 'vehicle_fitness', 10),
        doc('c', 'tenant', 't1', 'insurance_policy', 60),
        doc('e', 'warehouse', 'w1', 'peso_form_f', 80),
      ],
    });
    httpMock.expectOne('http://test/api/v1/warehouses/w1/documents').flush({ items: [], total: 0 });

    const rows = component['upcomingRows']();
    expect(rows.map((r) => [r.owner, r.document, r.urgency])).toEqual([
      ['Driver · Ravi Kumar', 'Driving licence', 'overdue'],
      ['Vehicle · MH12AB1234', 'Fitness certificate', 'due_soon'],
      ['Agency', 'Agency insurance', 'upcoming'],
      ['Warehouse · Main godown', 'PESO Form F', 'upcoming'],
    ]);
    expect(component['overdueCount']()).toBe(1);
  });

  it('switches warehouse documents when the selection changes', () => {
    flushInit();

    component['onWarehouseChange']('w2');
    httpMock.expectOne('http://test/api/v1/warehouses/w2/documents').flush({ items: [], total: 0 });
    expect(component['selectedWarehouseId']()).toBe('w2');
  });

  it('addWarehouseDocument posts against the selected warehouse', () => {
    flushInit();

    component['addWarehouseDocument']('w1')({
      doc_type: 'peso_form_f',
      document_number: 'X',
      file_ref: 'ref',
    }).subscribe();
    const req = httpMock.expectOne('http://test/api/v1/warehouses/w1/documents');
    expect(req.request.method).toBe('POST');
    req.flush({});
  });

  it('addTenantDocument posts to the tenant-scoped endpoint', () => {
    flushInit();

    component['addTenantDocument']({
      doc_type: 'insurance_policy',
      document_number: 'X',
      file_ref: 'ref',
    }).subscribe();
    const req = httpMock.expectOne('http://test/api/v1/tenant/documents');
    expect(req.request.method).toBe('POST');
    req.flush({});
  });
});

describe('expiry helpers', () => {
  const today = new Date(2026, 9, 20);

  it('counts whole days to the due date', () => {
    expect(daysUntil('2026-10-20', today)).toBe(0);
    expect(daysUntil('2026-10-19', today)).toBe(-1);
    expect(daysUntil('2026-11-19', today)).toBe(30);
  });

  it('classifies overdue, due soon (30 days) and upcoming', () => {
    expect(expiryUrgency('2026-10-19', today)).toBe('overdue');
    expect(expiryUrgency('2026-11-19', today)).toBe('due_soon');
    expect(expiryUrgency('2026-11-20', today)).toBe('upcoming');
  });
});
