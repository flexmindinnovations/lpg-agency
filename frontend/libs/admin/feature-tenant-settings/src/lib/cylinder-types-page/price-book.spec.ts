import type { PriceListEntryResponse } from '@lpg/shared/data-access';
import {
  currentPrices,
  defaultCustomerType,
  includesGstFrom,
  otherPrices,
  priceHeadline,
  priceHeadlineText,
  priceHint,
  usualGstRate,
  gstRateWarning,
} from './price-book';

function price(
  id: string,
  amount: string,
  from: string,
  overrides: Partial<PriceListEntryResponse> = {},
): PriceListEntryResponse {
  return {
    id,
    cylinder_type_id: 'c1',
    customer_type: 'domestic',
    branch_id: null,
    price: amount,
    effective_from: from,
    ...overrides,
  };
}

const NOW = new Date('2026-06-01T00:00:00Z');
const OLD = price('old', '800.00', '2026-01-01T00:00:00Z');
const NEW = price('new', '853.00', '2026-05-01T00:00:00Z');
const LATER = price('later', '900.00', '2026-07-01T00:00:00Z');
const BRANCH = price('branch', '860.00', '2026-02-01T00:00:00Z', { branch_id: 'b1' });
const OTHER_CYLINDER = price('x', '1.00', '2026-05-01T00:00:00Z', { cylinder_type_id: 'c2' });
const ALL = [OLD, NEW, LATER, BRANCH, OTHER_CYLINDER];

describe('the price list', () => {
  it('takes the newest price that has started, for each customer and branch', () => {
    expect(currentPrices(ALL, 'c1', NOW).map((p) => p.id)).toEqual(['new', 'branch']);
  });

  it('keeps older and not-yet-started prices apart, newest first', () => {
    expect(otherPrices(ALL, 'c1', NOW).map((p) => p.id)).toEqual(['later', 'old']);
  });

  it('shows the all-branches price of the usual customer, and counts the rest', () => {
    const industrial = price('industrial', '1500.00', '2026-03-01T00:00:00Z', {
      customer_type: 'industrial',
    });

    const headline = priceHeadline([...ALL, industrial], 'c1', 'domestic', NOW);

    expect(headline.entry?.id).toBe('new');
    expect(headline.others).toBe(2);
    expect(priceHeadlineText(headline)).toMatch(/853.*\+2 more$/);
  });

  it('shows whatever price there is when the usual one is missing', () => {
    expect(priceHeadline([BRANCH], 'c1', 'commercial', NOW).entry?.id).toBe('branch');
  });

  it('says when no price is in force', () => {
    expect(priceHeadlineText(priceHeadline([LATER], 'c1', 'domestic', NOW))).toBe('Not set');
  });

  it('starts a cylinder on its usual customer and GST rate', () => {
    expect([defaultCustomerType('domestic'), usualGstRate('domestic')]).toEqual(['domestic', 5]);
    expect([defaultCustomerType('commercial'), usualGstRate('commercial')]).toEqual([
      'commercial',
      18,
    ]);
    expect(usualGstRate(null)).toBeNull();
  });
});

describe('a GST rate that is not the usual one', () => {
  it('is pointed out for a commercial or a domestic cylinder', () => {
    expect(gstRateWarning('commercial', '5.00')).toBe(
      'GST on commercial LPG is usually 18%, not 5%. Check with your accountant.',
    );
    expect(gstRateWarning('domestic', 18)).toContain('usually 5%, not 18%');
  });

  it('says nothing for the usual rate, no rate or an unknown type', () => {
    expect(
      [
        gstRateWarning('commercial', '18.00'),
        gstRateWarning('domestic', 5),
        gstRateWarning('commercial', null),
        gstRateWarning('commercial', ''),
        gstRateWarning(null, '5.00'),
      ].filter(Boolean),
    ).toEqual([]);
  });
});

describe('the words around a price', () => {
  it('reads the GST setting the way the server does', () => {
    expect([true, 'yes', ' Inclusive ', 1].map(includesGstFrom)).toEqual([true, true, true, true]);
    expect([false, 'no', null, undefined, 0].map(includesGstFrom)).toEqual([
      false,
      false,
      false,
      false,
      false,
    ]);
  });

  it('works out what the customer pays when prices are before GST', () => {
    expect(priceHint(false, 18, 1000)).toContain('1,180');
    expect(priceHint(false, '5.00', '853')).toContain('895.65');
    expect(priceHint(false, null, 853)).toBe('Before GST. GST is added on the bill.');
  });

  it('says the price already includes GST when the agency set it up so', () => {
    expect(priceHint(true, 18, 1000)).toBe('Includes GST. This is what the customer pays.');
  });
});
