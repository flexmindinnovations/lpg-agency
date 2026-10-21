import { gstinIsValid, kycNumberError, verhoeffIsValid } from './identifier-validators';

describe('identifier validators', () => {
  it('checks the Aadhaar check digit', () => {
    expect(verhoeffIsValid('234123412346')).toBe(true);
    expect(kycNumberError('aadhaar', '2341 2341 2346')).toBeNull();
    expect(kycNumberError('aadhaar', '234123412345')).toContain('12-digit');
    expect(kycNumberError('aadhaar', '1234')).toContain('12-digit');
  });

  it('checks PAN, Voter ID, passport and licence formats', () => {
    expect(kycNumberError('pan', 'abcpe1234f')).toBeNull();
    expect(kycNumberError('pan', 'ABCDE1234F')).toContain('PAN');
    expect(kycNumberError('voter_id', 'ABC1234567')).toBeNull();
    expect(kycNumberError('passport', 'K1234567')).toBeNull();
    expect(kycNumberError('driving_license', 'MH12 20110012345')).toBeNull();
  });

  it('checks the GSTIN check character', () => {
    expect(gstinIsValid('27AAPFU0939F1ZV')).toBe(true);
    expect(gstinIsValid('27AAPFU0939F1ZA')).toBe(false);
  });
});
