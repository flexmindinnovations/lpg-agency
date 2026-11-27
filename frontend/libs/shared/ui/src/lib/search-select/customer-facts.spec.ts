import { customerFacts } from './customer-facts';

describe('customerFacts', () => {
  it('lists the phone and consumer number of an active customer', () => {
    expect(
      customerFacts({ phone_number: '98000 00000', consumer_number: 'C-12', status: 'active' }),
    ).toBe('98000 00000 · C-12');
  });

  it('names a status that is not active and skips a missing consumer number', () => {
    expect(
      customerFacts({ phone_number: '98000 00000', consumer_number: null, status: 'blocked' }),
    ).toBe('98000 00000 · Blocked');
  });
});
