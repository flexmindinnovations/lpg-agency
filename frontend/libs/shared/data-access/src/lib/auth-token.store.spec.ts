import { AuthTokenStore, type AuthPrincipal } from './auth-token.store';

describe('AuthTokenStore.defaultBranchIdAmong', () => {
  const principal = (branchId: string | null): AuthPrincipal => ({
    userId: 'u1',
    tenantId: 't1',
    role: 'manager',
    permissions: new Set(),
    email: null,
    branchId,
  });
  const branches = [{ id: 'b1' }, { id: 'b2' }];

  it("pre-selects the staff member's own branch", () => {
    const store = new AuthTokenStore();
    store.setSession('token', principal('b2'));

    expect(store.defaultBranchIdAmong(branches)).toBe('b2');
  });

  it('leaves the choice open for a tenant-wide user with several branches', () => {
    const store = new AuthTokenStore();
    store.setSession('token', principal(null));

    expect(store.defaultBranchIdAmong(branches)).toBeNull();
  });

  it('uses the only branch there is', () => {
    const store = new AuthTokenStore();

    expect(store.defaultBranchIdAmong([{ id: 'b9' }])).toBe('b9');
  });

  it('ignores a home branch that is not among the options', () => {
    const store = new AuthTokenStore();
    store.setSession('token', principal('gone'));

    expect(store.defaultBranchIdAmong(branches)).toBeNull();
  });
});
