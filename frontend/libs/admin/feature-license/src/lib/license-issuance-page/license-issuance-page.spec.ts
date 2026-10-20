import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import { of } from 'rxjs';
import { AgencyService, LicenseService, NotifyService } from '@lpg/shared/data-access';
import { LicenseIssuancePage } from './license-issuance-page';

const PENDING = {
  tenant_id: 't-pending',
  tenant_name: 'Pending Gas',
  status: 'pending_activation',
  plan_tier: 'standard',
  key_prefix: 'LPG-AB12',
  issued_at: '2026-10-01T00:00:00Z',
  expires_at: '2027-10-01T00:00:00Z',
};
const ISSUED = { tenant_id: 't-pending', plaintext_key: 'LPG-NEW-KEY', key_prefix: 'LPG-NEW' };

describe('LicenseIssuancePage', () => {
  let licenseService: Record<string, jest.Mock>;
  let confirmations: Confirmation[];

  function render() {
    confirmations = [];
    licenseService = {
      listLicenses: jest.fn().mockReturnValue(of([PENDING])),
      activateOnBehalfOf: jest.fn().mockReturnValue(of({ ...PENDING, status: 'active' })),
      replaceKey: jest.fn().mockReturnValue(of(ISSUED)),
      issueLicense: jest.fn(),
      revokeLicense: jest.fn().mockReturnValue(of(undefined)),
    };
    TestBed.configureTestingModule({
      imports: [LicenseIssuancePage],
      providers: [
        provideNoopAnimations(),
        { provide: LicenseService, useValue: licenseService },
        {
          provide: AgencyService,
          useValue: {
            listAgencies: () =>
              of([
                { id: 't-pending', name: 'Pending Gas', slug: 'pending', status: 'trial' },
                { id: 't-new', name: 'New Gas', slug: 'new', status: 'trial' },
                { id: 't-active', name: 'Active Gas', slug: 'active', status: 'active' },
              ]),
          },
        },
        { provide: NotifyService, useValue: { success: jest.fn(), error: jest.fn() } },
        {
          provide: ConfirmationService,
          useValue: { confirm: (c: Confirmation) => confirmations.push(c) },
        },
      ],
    });
    const fixture = TestBed.createComponent(LicenseIssuancePage);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('offers only agencies without a license when issuing', () => {
    const page = render();

    const options = page['unlicensedAgencyOptions']().map((o: { value: string }) => o.value);

    expect(options).toEqual(['t-new', 't-active']);
  });

  it('activates a pending license with a pasted key', () => {
    const page = render();
    page['openDetails'](PENDING as never);
    page['activateForm'].setValue({ key: '  LPG-PASTED  ' });

    page['activateWithKey']('t-pending');

    expect(licenseService['activateOnBehalfOf']).toHaveBeenCalledWith('t-pending', 'LPG-PASTED');
  });

  it('generates a new key after confirmation and shows it once', () => {
    const page = render();

    page['confirmReplaceKey'](PENDING as never);
    expect(licenseService['replaceKey']).not.toHaveBeenCalled();
    confirmations[0].accept?.();

    expect(licenseService['replaceKey']).toHaveBeenCalledWith('t-pending');
    expect(page['issuedKey']()).toEqual(ISSUED);
  });

  it('asks before closing the issued-key dialog without activating', () => {
    const page = render();
    page['issuedKey'].set(ISSUED as never);

    page['closeIssuedKeyDialog']();
    expect(page['issuedKey']()).not.toBeNull();
    confirmations[0].accept?.();

    expect(page['issuedKey']()).toBeNull();
  });

  it('asks before revoking', () => {
    const page = render();

    page['confirmRevoke'](PENDING as never);
    expect(licenseService['revokeLicense']).not.toHaveBeenCalled();
    confirmations[0].accept?.();

    expect(licenseService['revokeLicense']).toHaveBeenCalledWith('t-pending');
  });
});
