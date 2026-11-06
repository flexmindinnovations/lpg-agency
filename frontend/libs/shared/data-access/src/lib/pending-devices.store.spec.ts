import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { LicenseService } from './license.service';
import { PendingDevicesStore } from './pending-devices.store';

describe('PendingDevicesStore', () => {
  function setup(pendingDeviceCount: jest.Mock) {
    TestBed.configureTestingModule({
      providers: [{ provide: LicenseService, useValue: { pendingDeviceCount } }],
    });
    return TestBed.inject(PendingDevicesStore);
  }

  it('starts at zero without touching the server', () => {
    const count = jest.fn();
    const store = setup(count);

    expect(store.count()).toBe(0);
    expect(count).not.toHaveBeenCalled();
  });

  it('holds the number the server last reported', () => {
    const store = setup(jest.fn().mockReturnValue(of(3)));

    store.refresh();

    expect(store.count()).toBe(3);
  });

  it('keeps the last known number when a refresh fails', () => {
    const count = jest
      .fn()
      .mockReturnValueOnce(of(2))
      .mockReturnValueOnce(throwError(() => 500));
    const store = setup(count);

    store.refresh();
    store.refresh();

    expect(store.count()).toBe(2);
  });

  it('can be set directly and cleared', () => {
    const store = setup(jest.fn());

    store.set(4);
    expect(store.count()).toBe(4);
    store.clear();
    expect(store.count()).toBe(0);
  });
});
