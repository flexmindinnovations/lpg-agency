import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureComplianceCalendar } from './feature-compliance-calendar';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

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

  it('should create', () => {
    expect(component).toBeTruthy();
    fixture.detectChanges();
    httpMock.expectOne('http://test/api/v1/admin/warehouses').flush([]);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });
  });

  it('auto-selects the first warehouse and loads its documents on init', () => {
    fixture.detectChanges();
    httpMock
      .expectOne('http://test/api/v1/admin/warehouses')
      .flush([
        { id: 'w1', branch_id: 'b1', name: 'Warehouse 1', address_line: 'Line 1' },
        { id: 'w2', branch_id: 'b1', name: 'Warehouse 2', address_line: 'Line 2' },
      ]);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });

    expect(component['selectedWarehouseId']()).toBe('w1');
    httpMock
      .expectOne('http://test/api/v1/warehouses/w1/documents')
      .flush({ items: [], total: 0 });
  });

  it('switches warehouse documents when the selection changes', () => {
    fixture.detectChanges();
    httpMock.expectOne('http://test/api/v1/admin/warehouses').flush([]);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });

    component['onWarehouseChange']('w2');
    httpMock
      .expectOne('http://test/api/v1/warehouses/w2/documents')
      .flush({ items: [], total: 0 });
    expect(component['selectedWarehouseId']()).toBe('w2');
  });

  it('addWarehouseDocument posts against the selected warehouse', () => {
    fixture.detectChanges();
    httpMock.expectOne('http://test/api/v1/admin/warehouses').flush([]);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });

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
    fixture.detectChanges();
    httpMock.expectOne('http://test/api/v1/admin/warehouses').flush([]);
    httpMock.expectOne('http://test/api/v1/tenant/documents').flush({ items: [], total: 0 });

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
