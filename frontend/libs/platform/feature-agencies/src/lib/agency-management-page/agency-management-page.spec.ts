import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import type { FormGroup } from '@angular/forms';
import { of, throwError } from 'rxjs';
import { MessageService } from 'primeng/api';
import {
  AgencyService,
  ApiConfiguration,
  type AgencyUserSetupResponse,
  type CreateAgencyResponse,
  type StaffUserResponse,
  type TenantResponse,
} from '@lpg/shared/data-access';
import { AgencyManagementPage, suggestAgencyCode } from './agency-management-page';

const AGENCY: TenantResponse = {
  id: 't-1',
  name: 'Orient LPG Agency',
  slug: 'orient-lpg',
  status: 'trial',
  subscription_plan: 'standard',
  primary_contact_email: 'ops@orient.example',
  country: 'IN',
};

const CREATED: CreateAgencyResponse = {
  tenant: AGENCY,
  admin_user_id: 'u-1',
  admin_email: 'admin@orient.example',
  setup_path: '/reset-password?token=abc123',
  setup_token_expires_at: '2026-09-26T10:00:00Z',
};

const ADMIN: StaffUserResponse = {
  id: 'u-1',
  email: 'admin@orient.example',
  role: 'agency_admin',
  branch_id: null,
  is_active: true,
};

const MANAGER: StaffUserResponse = {
  id: 'u-2',
  email: 'manager@orient.example',
  role: 'manager',
  branch_id: null,
  is_active: true,
};

const ISSUED: AgencyUserSetupResponse = {
  user_id: 'u-1',
  email: 'admin@orient.example',
  role: 'agency_admin',
  setup_path: '/reset-password?token=fresh999',
  setup_token_expires_at: '2026-09-27T10:00:00Z',
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

/** The page's members are `protected`; tests reach them through this view. */
interface PageInternals {
  form: FormGroup;
  adminForm: FormGroup;
  submit(): void;
  openDetails(agency: TenantResponse): void;
  toggleAddAdmin(): void;
  addAdmin(agency: TenantResponse): void;
  issueSetupLink(agency: TenantResponse, user: StaffUserResponse): void;
  setupLink(): { heading: string; email: string; path: string } | null;
  setupLinkDrawerVisible(): boolean;
  setupUrl(): string;
  submitting(): boolean;
  acting(): boolean;
  users(): StaffUserResponse[];
  usersLoading(): boolean;
  addAdminOpen(): boolean;
}

describe('AgencyManagementPage', () => {
  let component: AgencyManagementPage;
  let fixture: ComponentFixture<AgencyManagementPage>;
  let agencyService: {
    listAgencies: jest.Mock;
    create: jest.Mock;
    listUsers: jest.Mock;
    addAdmin: jest.Mock;
    issueSetupLink: jest.Mock;
  };

  const page = () => component as unknown as PageInternals;

  const fill = (overrides: Record<string, string> = {}) => {
    const { form } = page();
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
    agencyService = {
      listAgencies: jest.fn(() => of([])),
      create: jest.fn(),
      listUsers: jest.fn(() => of([ADMIN, MANAGER])),
      addAdmin: jest.fn(),
      issueSetupLink: jest.fn(),
    };

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

  describe('create agency', () => {
    it('suggests an agency code while the user has not edited it', () => {
      const { form } = page();

      form.controls['name'].setValue('Sunrise Gas Agency');

      expect(form.controls['slug'].value).toBe('sunrise-gas-agency');
    });

    it('stops suggesting once the user edits the code', () => {
      const { form } = page();
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
      expect(page().setupLink()?.heading).toBe('Agency created');
      expect(page().setupLink()?.email).toBe('admin@orient.example');
      expect(page().setupLinkDrawerVisible()).toBe(true);
      expect(page().setupUrl()).toContain('/reset-password?token=abc123');
      expect(page().submitting()).toBe(false);
    });

    it('keeps the form open and re-enables submit when the API rejects the request', () => {
      agencyService.create.mockReturnValue(throwError(() => new Error('409')));
      fill();

      page().submit();

      expect(page().setupLink()).toBeNull();
      expect(page().submitting()).toBe(false);
    });
  });

  describe('agency users', () => {
    it("loads the agency's users when its details open", () => {
      page().openDetails(AGENCY);

      expect(agencyService.listUsers).toHaveBeenCalledWith('t-1');
      expect(page().users()).toEqual([ADMIN, MANAGER]);
      expect(page().usersLoading()).toBe(false);
    });

    it('shows an empty list rather than stale users when the load fails', () => {
      agencyService.listUsers.mockReturnValue(throwError(() => new Error('boom')));

      page().openDetails(AGENCY);

      expect(page().users()).toEqual([]);
      expect(page().usersLoading()).toBe(false);
    });

    it('does not call the API for an invalid new-admin email', () => {
      page().openDetails(AGENCY);
      page().adminForm.setValue({ email: 'nope' });

      page().addAdmin(AGENCY);

      expect(agencyService.addAdmin).not.toHaveBeenCalled();
    });

    it('adds an admin, refreshes the list and shows their one-time link', () => {
      agencyService.addAdmin.mockReturnValue(of(ISSUED));
      page().openDetails(AGENCY);
      page().toggleAddAdmin();
      page().adminForm.setValue({ email: 'second@orient.example' });
      agencyService.listUsers.mockClear();

      page().addAdmin(AGENCY);

      expect(agencyService.addAdmin).toHaveBeenCalledWith('t-1', 'second@orient.example');
      expect(agencyService.listUsers).toHaveBeenCalledWith('t-1');
      expect(page().setupLink()?.heading).toBe('Admin added');
      expect(page().setupUrl()).toContain('/reset-password?token=fresh999');
      expect(page().addAdminOpen()).toBe(false);
      expect(page().acting()).toBe(false);
    });

    it('keeps the add-admin form open when the API rejects it (e.g. email already used)', () => {
      agencyService.addAdmin.mockReturnValue(throwError(() => new Error('409')));
      page().openDetails(AGENCY);
      page().toggleAddAdmin();
      page().adminForm.setValue({ email: 'taken@orient.example' });

      page().addAdmin(AGENCY);

      expect(page().addAdminOpen()).toBe(true);
      expect(page().setupLink()).toBeNull();
      expect(page().acting()).toBe(false);
    });

    it('issues a new setup link for an admin and shows it', () => {
      agencyService.issueSetupLink.mockReturnValue(of(ISSUED));
      page().openDetails(AGENCY);

      page().issueSetupLink(AGENCY, ADMIN);

      expect(agencyService.issueSetupLink).toHaveBeenCalledWith('t-1', 'u-1');
      expect(page().setupLink()?.heading).toBe('New setup link');
      expect(page().setupLink()?.email).toBe('admin@orient.example');
      expect(page().setupUrl()).toContain('/reset-password?token=fresh999');
      expect(page().acting()).toBe(false);
    });

    it('re-enables the button when issuing a link fails', () => {
      agencyService.issueSetupLink.mockReturnValue(throwError(() => new Error('404')));
      page().openDetails(AGENCY);

      page().issueSetupLink(AGENCY, ADMIN);

      expect(page().setupLink()).toBeNull();
      expect(page().acting()).toBe(false);
    });
  });
});
