import { BOOKING_SOURCE_LABELS, bookingSourceLabel } from './format';

describe('bookingSourceLabel', () => {
  it('names every booking source the API accepts', () => {
    expect(Object.keys(BOOKING_SOURCE_LABELS).sort()).toEqual(
      ['api', 'mobile_app', 'phone', 'staff', 'walk_in', 'whatsapp'].sort(),
    );
  });

  it.each([
    ['mobile_app', 'Mobile app'],
    ['staff', 'Dashboard'],
    ['phone', 'Phone'],
    ['walk_in', 'Walk-in'],
    ['whatsapp', 'WhatsApp'],
    ['api', 'API'],
  ])('shows %s as "%s"', (value, label) => {
    expect(bookingSourceLabel(value)).toBe(label);
  });

  it('shows a dash for a missing value and passes an unknown one through', () => {
    expect(bookingSourceLabel(null)).toBe('—');
    expect(bookingSourceLabel('')).toBe('—');
    expect(bookingSourceLabel('carrier_pigeon')).toBe('carrier_pigeon');
  });
});
