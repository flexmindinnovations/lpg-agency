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
    const service = {
      get: jest.fn(() => of(profile)),
      save: jest.fn(() => of(profile)),
      verify: jest.fn(() => of({})),
    };
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

  it('fills a blank bank and branch from a verified IFSC, but never overwrites typed ones', () => {
    const { component, service } = create();
    service.verify.mockReturnValue(
      of({ ifsc: { status: 'verified', bank: 'ICICI Bank', branch: 'MG ROAD', city: 'PUNE' } }),
    );
    component.form.patchValue({ ifsc: 'ICIC0000001', bank_name: '', branch: 'Own branch' });
    (component as unknown as { verifyIfsc(): void }).verifyIfsc();
    expect(service.verify).toHaveBeenCalledWith({ ifsc: 'ICIC0000001' });
    expect(component.form.getRawValue().bank_name).toBe('ICICI Bank');
    expect(component.form.getRawValue().branch).toBe('Own branch');
  });

  it('blocks saving an IFSC that no bank branch holds', () => {
    const { component, service } = create();
    service.verify.mockReturnValue(of({ ifsc: { status: 'not_found' } }));
    component.form.patchValue({ ifsc: 'ABCD0123456' });
    component.form.markAsDirty();
    (component as unknown as { verifyIfsc(): void }).verifyIfsc();
    expect(component.form.controls.ifsc.errors).toHaveProperty('notFound');
    (component as unknown as { save(): void }).save();
    expect(service.save).not.toHaveBeenCalled();
  });

  it('does not ask the server to verify a malformed IFSC or UPI ID', () => {
    const { component, service } = create();
    component.form.patchValue({ ifsc: 'HDFC123', upi_id: 'no-handle' });
    (component as unknown as { verifyIfsc(): void }).verifyIfsc();
    (component as unknown as { verifyUpi(): void }).verifyUpi();
    expect(service.verify).not.toHaveBeenCalled();
  });

  it('asks for a changed account number twice, and only a matching pair saves', () => {
    const { component, service } = create();
    component.form.patchValue({ account_number: '60200987654321' });
    component.form.markAsDirty();
    (component as unknown as { save(): void }).save();
    expect(component.form.controls.account_number_confirm.errors).toHaveProperty('mismatch');
    expect(service.save).not.toHaveBeenCalled();

    component.form.patchValue({ account_number_confirm: '6020 0987 654321' });
    (component as unknown as { save(): void }).save();
    expect(service.save).toHaveBeenCalledTimes(1);
    expect(service.save.mock.calls[0][0]).not.toHaveProperty('account_number_confirm');
  });

  it('does not ask to re-type an account number that is already saved', () => {
    const { component, service } = create();
    component.form.markAsDirty();
    (component as unknown as { save(): void }).save();
    expect(service.save).toHaveBeenCalledTimes(1);
  });
});
