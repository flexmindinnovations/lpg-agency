import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import {
  AdminStaffUserService,
  AuthService,
  NotifyService,
  type StaffUserResponse,
} from '@lpg/shared/data-access';
import { StaffUsersPage } from './staff-users-page';

const user = (id: string, role: string, isActive = true): StaffUserResponse => ({
  id,
  email: `${id}@example.com`,
  role,
  branch_id: null,
  is_active: isActive,
  display_name: id === 'u2' ? 'Ravi Kumar' : null,
  contact_phone: null,
});

type Row = { id: string; name: string; isSelf: boolean; is_active: boolean };
type Column = {
  header: string;
  valueFormatter: (v: unknown, r: Row) => string;
  onLinkClick: (r: Row) => void;
};
type Internals = {
  rows: () => Row[];
  columns: {
    header: string;
    valueFormatter?: (v: unknown, r: Row) => string;
    onLinkClick?: (r: Row) => void;
  }[];
};

describe('StaffUsersPage (DA-01)', () => {
  let deactivateStaffUser: jest.Mock;
  let reactivateStaffUser: jest.Mock;
  let confirm: jest.SpyInstance;
  let page: Internals;

  beforeEach(() => {
    deactivateStaffUser = jest.fn().mockReturnValue(of(undefined));
    reactivateStaffUser = jest.fn().mockReturnValue(of(undefined));
    TestBed.configureTestingModule({
      imports: [StaffUsersPage],
      providers: [
        ConfirmationService,
        {
          provide: AdminStaffUserService,
          useValue: {
            listStaffUsers: () =>
              of([
                user('me', 'agency_admin'),
                user('u2', 'dispatcher'),
                user('u3', 'accountant', false),
              ]),
            deactivateStaffUser,
            reactivateStaffUser,
          },
        },
        { provide: AuthService, useValue: { principal: signal({ userId: 'me' }) } },
        { provide: NotifyService, useValue: { success: jest.fn(), error: jest.fn() } },
      ],
    });
    confirm = jest.spyOn(TestBed.inject(ConfirmationService), 'confirm');
    const fixture = TestBed.createComponent(StaffUsersPage);
    fixture.detectChanges();
    page = fixture.componentInstance as unknown as Internals;
  });

  const action = (): Column => {
    const column = page.columns.find((c) => c.header === 'Action');
    if (!column) throw new Error('no Action column');
    return column;
  };
  const row = (id: string): Row => {
    const found = page.rows().find((r) => r.id === id);
    if (!found) throw new Error(`no row ${id}`);
    return found;
  };

  it('shows names, marks your own row and offers no action on it', () => {
    expect(row('u2').name).toBe('Ravi Kumar');
    expect(row('me').isSelf).toBe(true);
    expect(action().valueFormatter(null, row('me'))).toBe('');
    action().onLinkClick(row('me'));
    expect(confirm).not.toHaveBeenCalled();
    expect(deactivateStaffUser).not.toHaveBeenCalled();
  });

  it('asks before deactivating and only deactivates on accept', () => {
    action().onLinkClick(row('u2'));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(deactivateStaffUser).not.toHaveBeenCalled();
    (confirm.mock.calls[0][0] as Confirmation).accept?.();
    expect(deactivateStaffUser).toHaveBeenCalledWith('u2');
  });

  it('reactivates a deactivated user', () => {
    expect(action().valueFormatter(null, row('u3'))).toBe('Reactivate');
    action().onLinkClick(row('u3'));
    expect(reactivateStaffUser).toHaveBeenCalledWith('u3');
  });
});
