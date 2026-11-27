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
type Action = {
  text: string;
  visible: (r: Row) => boolean;
  label: (r: Row) => string;
  onAction: (r: Row) => void;
};
type Internals = {
  rows: () => Row[];
  columns: { header: string; cellRendererParams?: { actions?: Action[] } }[];
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

  const actions = (): Action[] => {
    const column = page.columns.find((c) => c.header === 'Actions');
    if (!column?.cellRendererParams?.actions) throw new Error('no Actions column');
    return column.cellRendererParams.actions;
  };
  const offered = (r: Row) => actions().filter((a) => a.visible(r));
  const press = (r: Row, text: string) => {
    const button = offered(r).find((a) => a.text === text);
    if (!button) throw new Error(`no ${text} button`);
    button.onAction(r);
  };
  const row = (id: string): Row => {
    const found = page.rows().find((r) => r.id === id);
    if (!found) throw new Error(`no row ${id}`);
    return found;
  };

  it('shows names, marks your own row and offers no action on it', () => {
    expect(row('u2').name).toBe('Ravi Kumar');
    expect(row('me').isSelf).toBe(true);
    expect(offered(row('me'))).toEqual([]);
  });

  it('asks before deactivating and only deactivates on accept', () => {
    expect(offered(row('u2')).map((a) => a.label(row('u2')))).toEqual(['Deactivate Ravi Kumar']);
    press(row('u2'), 'Deactivate');
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(deactivateStaffUser).not.toHaveBeenCalled();
    (confirm.mock.calls[0][0] as Confirmation).accept?.();
    expect(deactivateStaffUser).toHaveBeenCalledWith('u2');
  });

  it('reactivates a deactivated user', () => {
    expect(offered(row('u3')).map((a) => a.text)).toEqual(['Reactivate']);
    press(row('u3'), 'Reactivate');
    expect(reactivateStaffUser).toHaveBeenCalledWith('u3');
  });
});
