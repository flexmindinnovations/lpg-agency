import { roleLabel } from './role-labels';

describe('roleLabel', () => {
  it('names known roles', () => {
    expect(roleLabel('agency_admin')).toBe('Agency Admin');
    expect(roleLabel('warehouse_staff')).toBe('Warehouse Staff');
  });

  it('sentence-cases unknown codes and tolerates empty input', () => {
    expect(roleLabel('field_auditor')).toBe('Field auditor');
    expect(roleLabel(null)).toBe('');
  });
});
