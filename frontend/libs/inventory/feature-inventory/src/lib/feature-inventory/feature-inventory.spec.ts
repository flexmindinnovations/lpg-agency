import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureInventory } from './feature-inventory';
import {
  ApiConfiguration,
  NotifyService,
  globalErrorToastInterceptor,
  problemDetailsInterceptor,
} from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

const TRANSITIONS = {
  status_change: { filled: ['damaged', 'leakage'], empty: ['damaged'], scrap: [] },
  adjustment: { filled: ['damaged', 'leakage'], leakage: ['filled'], scrap: [] },
};

describe('FeatureInventory', () => {
  let component: FeatureInventory;
  let fixture: ComponentFixture<FeatureInventory>;
  let httpMock: HttpTestingController;
  const notify = { success: jest.fn(), error: jest.fn() };

  // Protected members read through a typed view, as other specs here do.
  const c = () => component as unknown as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

  beforeEach(async () => {
    notify.success.mockReset();
    notify.error.mockReset();
    await TestBed.configureTestingModule({
      imports: [FeatureInventory],
      providers: [
        provideHttpClient(
          withInterceptors([globalErrorToastInterceptor, problemDetailsInterceptor]),
        ),
        provideHttpClientTesting(),
        provideRouter([]),
        MessageService,
        { provide: NotifyService, useValue: notify },
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureInventory);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    component.ngOnInit();
    httpMock.expectOne('http://test/api/v1/inventory/status-transitions').flush(TRANSITIONS);
    httpMock.match(() => true).forEach((r) => r.flush([]));
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('offers only the moves the domain allows (DA-17)', () => {
    expect(
      c()
        ['toStatusOptions']('status_change', 'filled')
        .map((o: { value: string }) => o.value),
    ).toEqual(['damaged', 'leakage']);
    expect(
      c()
        ['fromStatusOptions']('status_change')
        .map((o: { value: string }) => o.value),
    ).toEqual(['filled', 'empty']);
    // Adjustments may undo a status move.
    expect(c()['toStatusOptions']('adjustment', 'leakage')).toEqual([
      { label: 'Filled', value: 'filled' },
    ]);
  });

  it('moves "To" onto an allowed target when "From" changes', () => {
    c()['openStatusChangeModal']();
    const form = c()['statusChangeForm'];
    expect(form.controls.to_status.value).toBe('damaged');

    form.controls.from_status.setValue('empty');
    expect(form.controls.to_status.value).toBe('damaged');
    form.controls.to_status.setValue('damaged');
    form.controls.from_status.setValue('scrap');
    expect(form.controls.to_status.value).toBe('');
  });

  it('sends the OMC code and document numbers with a GRN (DA-02, DA-34)', () => {
    c()['locationRefId'].set('w1');
    c()['openGrnModal']();
    c()['grnForm'].setValue({
      cylinder_type_id: 'ct1',
      quantity_received: 10,
      source_omc: 'hpcl',
      challan_number: ' ch-1 ',
      invoice_number: '',
      truck_number: 'TS09AB1234',
    });
    c()['onSubmitGrn']();

    const req = httpMock.expectOne('http://test/api/v1/warehouses/w1/goods-receipt-notes');
    expect(req.request.body).toEqual({
      cylinder_type_id: 'ct1',
      quantity_received: 10,
      source_omc: 'hpcl',
      challan_number: 'ch-1',
      invoice_number: null,
      truck_number: 'TS09AB1234',
    });
  });

  it('shows a failed drawer request inside the drawer only, and clears it on reopen (DA-16)', () => {
    c()['locationRefId'].set('w1');
    c()['openAdjustModal']();
    c()['adjustForm'].patchValue({ cylinder_type_id: 'ct1', reason: 'broken valve' });
    c()['onSubmitAdjust']();

    httpMock
      .expectOne((r) => r.url.endsWith('/adjustments'))
      .flush(
        { error_code: 'INSUFFICIENT_STOCK', title: 'Insufficient stock', detail: 'x', status: 409 },
        { status: 409, statusText: 'Conflict' },
      );

    expect(c()['drawerError']()).toBe('Not enough stock available for that quantity.');
    expect(c()['errorMessage']()).toBeNull();
    expect(notify.error).not.toHaveBeenCalled();

    c()['openAdjustModal']();
    expect(c()['drawerError']()).toBeNull();
  });

  it('explains a refused self-approval next to the pending count (DA-04)', () => {
    c()['onApproveCount']({ id: 'r1' });
    httpMock
      .expectOne('http://test/api/v1/reconciliation-records/r1/approve')
      .flush(
        { error_code: 'SELF_APPROVAL_NOT_ALLOWED', title: 'x', detail: 'x', status: 409 },
        { status: 409, statusText: 'Conflict' },
      );

    expect(c()['countsError']()).toBe(
      'You recorded this count, so someone else has to approve it.',
    );
    expect(notify.error).not.toHaveBeenCalled();
  });
});
