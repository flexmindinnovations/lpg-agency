import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { MessageService } from 'primeng/api';
import {
  AgencyService,
  ApiConfiguration,
  type CreateAgencyResponse,
} from '@lpg/shared/data-access';
import { AgencyManagementPage, suggestAgencyCode } from './agency-management-page';

const CREATED: CreateAgencyResponse = {
  tenant: {
    id: 't-1',
    name: 'Orient LPG Agency',
    slug: 'orient-lpg',
    status: 'trial',
    subscription_plan: 'standard',
    primary_contact_email: 'ops@orient.example',
    country: 'IN',
  },
  admin_user_id: 'u-1',
  admin_email: 'admin@orient.example',
  setup_path: '/reset-password?token=abc123',
  setup_token_expires_at: '2026-09-26T10:00:00Z',
};

describe('suggestAgencyCode', () => {
  it('turns a name into a lowercase hyphenated code', () => {
    expect(suggestAgencyCode('Orient LPG Agency')).toBe('orient-lpg-agency');
  });

  it('collapses punctuation and trims stray hyphens', () => {
    expect(suggestAgencyCode('  --Sri Gas & Co.!  ')).toBe('sri-gas-co');
  });

  it('caps the length at 40 without leaving a trailing hyphen', () => {
    const code = suggestAgencyCode('a'.repeat(39) + ' bcd');
    expect(code.length).toBeLessThanOrEqual(40);
    expect(code.endsWith('-')).toBe(false);
  });

  it('returns an empty string for a name with no usable characters', () => {
    expect(suggestAgencyCode('!!!')).toBe('');
  });
});

describe('AgencyManagementPage', () => {
  let component: AgencyManagementPage;
  let fixture: ComponentFixture<AgencyManagementPage>;
  let agencyService: { listAgencies: jest.Mock; create: jest.Mock };

  // `form`, `submit` and the signals are `protected` — reached via a cast in tests.
  const page = () =>
    component as unknown as {
      submit(): void;
      created(): CreateAgencyResponse | null;
      createdDrawerVisible(): boolean;
      submitting(): boolean;
      setupUrl(): string;
    };

  const fill = (overrides: Record<string, string> = {}) => {
    const form = (component as unknown as { form: import('@angular/forms').FormGroup }).form;
    form.setValue({
      name: 'Orient LPG Agency',
      slug: 'orient-lpg',
      primaryContactEmail: 'ops@orient.example',
      adminEmail: 'admin@orient.example',
      ...overrides,
    });
    return form;
  };

  beforeEach(async () => {
    agencyService = { listAgencies: jest.fn(() => of([])), create: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [AgencyManagementPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: AgencyService, useValue: agencyService },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AgencyManagementPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('suggests an agency code while the user has not edited it', () => {
    const form = (component as unknown as { form: import('@angular/forms').FormGroup }).form;

    form.controls['name'].setValue('Sunrise Gas Agency');

    expect(form.controls['slug'].value).toBe('sunrise-gas-agency');
  });

  it('stops suggesting once the user edits the code', () => {
    const form = (component as unknown as { form: import('@angular/forms').FormGroup }).form;
    form.controls['slug'].markAsDirty();
    form.controls['slug'].setValue('my-code');

    form.controls['name'].setValue('Something Else');

    expect(form.controls['slug'].value).toBe('my-code');
  });

  it.each(['UPPER', 'has space', '-lead', 'trail-', 'dou--ble', 'ab'])(
    'rejects the invalid agency code %p',
    (slug) => {
      expect(fill({ slug }).controls['slug'].valid).toBe(false);
    },
  );

  it('does not call the API while the form is invalid', () => {
    fill({ adminEmail: 'not-an-email' });

    page().submit();

    expect(agencyService.create).not.toHaveBeenCalled();
  });

  it('creates the agency and reveals the one-time setup link', () => {
    agencyService.create.mockReturnValue(of(CREATED));
    fill();

    page().submit();

    expect(agencyService.create).toHaveBeenCalledWith({
      name: 'Orient LPG Agency',
      slug: 'orient-lpg',
      primary_contact_email: 'ops@orient.example',
      admin_email: 'admin@orient.example',
    });
    expect(page().created()).toEqual(CREATED);
    expect(page().createdDrawerVisible()).toBe(true);
    expect(page().setupUrl()).toContain('/reset-password?token=abc123');
    expect(page().submitting()).toBe(false);
  });

  it('keeps the form open and re-enables submit when the API rejects the request', () => {
    agencyService.create.mockReturnValue(throwError(() => new Error('409')));
    fill();

    page().submit();

    expect(page().created()).toBeNull();
    expect(page().submitting()).toBe(false);
  });
});
