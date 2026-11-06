import {
  allowedActions,
  appWithVersion,
  historyVerb,
  osLabel,
  phoneModel,
  statusLabel,
  statusSeverity,
} from './device-labels';

describe('device labels', () => {
  it('uses plain words for each state', () => {
    expect(statusLabel('pending')).toBe('Waiting');
    expect(statusLabel('approved')).toBe('Approved');
    expect(statusLabel('blocked')).toBe('Blocked');
    expect(statusLabel('removed')).toBe('Removed');
    expect(statusLabel('mystery')).toBe('mystery');
  });

  it('colours waiting as a warning and blocked as danger', () => {
    expect(statusSeverity('pending')).toBe('warn');
    expect(statusSeverity('approved')).toBe('success');
    expect(statusSeverity('blocked')).toBe('danger');
    expect(statusSeverity('removed')).toBe('secondary');
    expect(statusSeverity('mystery')).toBe('secondary');
  });

  it('does not repeat the maker when the model already starts with it', () => {
    expect(phoneModel({ manufacturer: 'Xiaomi', model: 'Redmi 12' })).toBe('Xiaomi Redmi 12');
    expect(phoneModel({ manufacturer: 'samsung', model: 'Samsung Galaxy A14' })).toBe(
      'Samsung Galaxy A14',
    );
    expect(phoneModel({ manufacturer: 'Vivo', model: null })).toBe('Vivo');
    expect(phoneModel({ manufacturer: null, model: 'iPhone 13' })).toBe('iPhone 13');
    expect(phoneModel({ manufacturer: null, model: null })).toBe('—');
  });

  it('names the app with its version', () => {
    expect(appWithVersion({ app_type: 'driver_app', app_version: '1.4.0' })).toBe(
      'Driver app 1.4.0',
    );
    expect(appWithVersion({ app_type: 'admin_app', app_version: null })).toBe('Admin app');
  });

  it('shows the operating system, or a dash when the phone did not say', () => {
    expect(osLabel({ os_version: 'Android 13', platform: 'android' })).toBe('Android 13');
    expect(osLabel({ os_version: '17.2', platform: 'ios' })).toBe('iOS 17.2');
    expect(osLabel({ os_version: null, platform: null })).toBe('—');
  });

  it('offers only the moves the server allows', () => {
    expect(allowedActions('pending')).toEqual(['approve', 'block', 'remove']);
    expect(allowedActions('approved')).toEqual(['block', 'remove']);
    expect(allowedActions('blocked')).toEqual(['unblock', 'remove']);
    expect(allowedActions('removed')).toEqual([]);
  });

  it('words the history in plain English', () => {
    expect(historyVerb('registered')).toBe('Asked to be approved');
    expect(historyVerb('unblocked')).toBe('Unblocked');
    expect(historyVerb('weird')).toBe('weird');
  });
});
