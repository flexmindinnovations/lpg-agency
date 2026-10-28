import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { PaymentProfileService } from '@lpg/shared/data-access';
import { PaymentSettings } from './payment-settings';

describe('PaymentSettings', () => {
  const profile = {
    account_holder: 'Sai Gas Agency',
    bank_name: 'HDFC Bank',
    account_number: '50100123456789',
    ifsc: 'HDFC0001234',
    branch: 'Pune',
    upi_id: 'saigas@okhdfcbank',
    upi_payee_name: '',
    invoice_footer_note: '',
    has_bank_details: true,
    has_upi: true,
  };

  function create() {
    const service = { get: jest.fn(() => of(profile)), save: jest.fn(() => of(profile)) };
    TestBed.configureTestingModule({
      imports: [PaymentSettings],
      providers: [{ provide: PaymentProfileService, useValue: service }, MessageService],
    });
    const fixture = TestBed.createComponent(PaymentSettings);
    fixture.detectChanges();
    return { fixture, service, component: fixture.componentInstance };
  }

  it('fills the form from the saved profile', () => {
    const { component } = create();
    expect(component.form.getRawValue().upi_id).toBe('saigas@okhdfcbank');
    expect(component.form.pristine).toBe(true);
  });

  it('rejects a malformed IFSC and UPI ID without calling the server', () => {
    const { component, service } = create();
    component.form.patchValue({ ifsc: 'HDFC123', upi_id: 'no-handle' });
    component.form.markAsDirty();
    (component as unknown as { save(): void }).save();
    expect(component.form.controls.ifsc.errors).toHaveProperty('pattern');
    expect(component.form.controls.upi_id.errors).toHaveProperty('pattern');
    expect(service.save).not.toHaveBeenCalled();
  });

  it('saves a valid profile', () => {
    const { component, service } = create();
    component.form.patchValue({ ifsc: 'hdfc0001234' });
    component.form.markAsDirty();
    (component as unknown as { save(): void }).save();
    expect(service.save).toHaveBeenCalledTimes(1);
  });
});
