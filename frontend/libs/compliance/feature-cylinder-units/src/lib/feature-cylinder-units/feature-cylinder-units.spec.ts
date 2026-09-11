import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureCylinderUnits } from './feature-cylinder-units';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

describe('FeatureCylinderUnits', () => {
  let component: FeatureCylinderUnits;
  let fixture: ComponentFixture<FeatureCylinderUnits>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureCylinderUnits],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureCylinderUnits);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('offers only the domain-allowed next conditions for the selected unit', () => {
    component['selectedUnit'].set({
      id: 'u1',
      cylinder_type_id: 'ct1',
      serial_number: 'CYL-1',
      qr_code: 'CYL-1',
      manufacture_date: null,
      owner_omc: null,
      condition_status: 'filled',
      custody_type: 'warehouse',
      custody_ref_id: 'w1',
      last_tested_at: null,
      test_due_date: null,
      is_due_for_test: false,
      is_retired: false,
    });
    const allowed = component['allowedNextConditions']().map((o) => o.value);
    expect(allowed.sort()).toEqual(['empty', 'leakage']);
  });

  it('includes QR / Barcode column in grid definition', () => {
    const qrCol = component['columns'].find((c) => c.field === 'qr_code');
    expect(qrCol).toBeDefined();
    expect(qrCol?.header).toBe('QR / Barcode');
  });

  it('manages quick lookup dialog state correctly', () => {
    expect(component['showLookupModal']()).toBe(false);
    component['openLookupModal']();
    expect(component['showLookupModal']()).toBe(true);
    expect(component['lookupCode']()).toBe('');
    expect(component['lookupResult']()).toBeNull();
  });

  it('correctly tracks isAnyModalOpen for all action and utility modals', () => {
    expect(component['isAnyModalOpen']()).toBe(false);

    component['showMoveCustodyModal'].set(true);
    expect(component['isAnyModalOpen']()).toBe(true);
    component['showMoveCustodyModal'].set(false);

    component['showTestModal'].set(true);
    expect(component['isAnyModalOpen']()).toBe(true);
    component['showTestModal'].set(false);

    component['showConditionModal'].set(true);
    expect(component['isAnyModalOpen']()).toBe(true);
    component['showConditionModal'].set(false);

    component['showLookupModal'].set(true);
    expect(component['isAnyModalOpen']()).toBe(true);
    component['showLookupModal'].set(false);

    component['showRegisterModal'].set(true);
    expect(component['isAnyModalOpen']()).toBe(true);
    component['showRegisterModal'].set(false);

    expect(component['isAnyModalOpen']()).toBe(false);
  });

  it('does not close the detail drawer on Escape when a modal dialog is open', () => {
    component['showDetailDrawer'].set(true);
    component['showMoveCustodyModal'].set(true);

    component['onDocumentEscape']();

    expect(component['showDetailDrawer']()).toBe(true);
    expect(component['showMoveCustodyModal']()).toBe(true);
  });

  it('closes the detail drawer on Escape when no modal dialog is open', () => {
    component['showDetailDrawer'].set(true);

    component['onDocumentEscape']();

    expect(component['showDetailDrawer']()).toBe(false);
  });
});
