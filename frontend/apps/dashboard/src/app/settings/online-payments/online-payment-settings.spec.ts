import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ConfirmationService, MessageService } from 'primeng/api';
import { PaymentGatewayService } from '@lpg/shared/data-access';
import { OnlinePaymentSettings } from './online-payment-settings';

describe('OnlinePaymentSettings', () => {
  const none = { configured: false, source: 'platform' as const };
  const saved = {
    configured: true,
    source: 'agency' as const,
    mode: 'live' as const,
    key_id_masked: 'rzp_live_••••••3456',
    has_key_secret: true,
    has_webhook_secret: false,
    webhook_path: '/api/v1/payments/razorpay/webhook/abc',
  };

  function create(initial: object = none) {
    const service = {
      get: jest.fn(() => of(initial)),
      save: jest.fn(() => of(saved)),
      remove: jest.fn(() => of(undefined)),
      rotateWebhookUrl: jest.fn(() => of(saved)),
      test: jest.fn(() => of({ ok: true, message: 'Razorpay accepted this key.' })),
    };
    TestBed.configureTestingModule({
      imports: [OnlinePaymentSettings],
      providers: [
        { provide: PaymentGatewayService, useValue: service },
        MessageService,
        ConfirmationService,
      ],
    });
    const fixture = TestBed.createComponent(OnlinePaymentSettings);
    fixture.detectChanges();
    return { fixture, service, component: fixture.componentInstance };
  }

  const save = (c: OnlinePaymentSettings) => (c as unknown as { save(): void }).save();

  it('needs both the key id and the key secret the first time', () => {
    const { component, service } = create();
    save(component);
    expect(component.form.controls.key_id.errors).toHaveProperty('required');
    expect(component.form.controls.key_secret.errors).toHaveProperty('required');
    expect(service.save).not.toHaveBeenCalled();
  });

  it('rejects a key id that is not a Razorpay key', () => {
    const { component, service } = create();
    component.form.patchValue({ key_id: 'pk_live_nope', key_secret: 'x' });
    component.form.markAsDirty();
    save(component);
    expect(component.form.controls.key_id.errors).toHaveProperty('pattern');
    expect(service.save).not.toHaveBeenCalled();
  });

  it('saves the key and clears the secret fields afterwards', () => {
    const { component, service } = create();
    component.form.patchValue({ key_id: ' rzp_live_AbCdEf123456 ', key_secret: 's3cret' });
    component.form.markAsDirty();
    save(component);
    expect(service.save).toHaveBeenCalledWith({
      key_id: 'rzp_live_AbCdEf123456',
      key_secret: 's3cret',
      webhook_secret: '',
    });
    expect(component.form.getRawValue().key_secret).toBe('');
  });

  it('lets a saved key be left blank so only a webhook secret changes', () => {
    const { component, service } = create(saved);
    component.form.patchValue({ webhook_secret: 'whsec' });
    component.form.markAsDirty();
    save(component);
    expect(service.save).toHaveBeenCalledWith({
      key_id: '',
      key_secret: '',
      webhook_secret: 'whsec',
    });
  });

  it('shows the agency webhook address on this site', () => {
    const { fixture } = create(saved);
    expect(fixture.nativeElement.textContent).toContain(
      `${window.location.origin}/api/v1/payments/razorpay/webhook/abc`,
    );
  });

  it('never prints a secret field value in the page', () => {
    const { fixture } = create(saved);
    expect(fixture.nativeElement.textContent).not.toContain('s3cret');
  });
});
