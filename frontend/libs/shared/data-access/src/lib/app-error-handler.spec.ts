import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { AppErrorHandler } from './app-error-handler';
import { NotifyService } from './services/notify.service';

describe('AppErrorHandler', () => {
  let notify: { error: jest.Mock };
  let handler: AppErrorHandler;

  beforeEach(() => {
    notify = { error: jest.fn() };
    TestBed.configureTestingModule({
      providers: [AppErrorHandler, { provide: NotifyService, useValue: notify }],
    });
    handler = TestBed.inject(AppErrorHandler);
  });

  it('shows unexpected errors to the user', () => {
    handler.handleError(new Error('boom'));
    expect(notify.error).toHaveBeenCalledTimes(1);
  });

  it('shows one message per burst', () => {
    handler.handleError(new Error('a'));
    handler.handleError(new Error('b'));
    expect(notify.error).toHaveBeenCalledTimes(1);
  });

  it('leaves session-expiry 401s to the session dialog', () => {
    handler.handleError(new HttpErrorResponse({ status: 401 }));
    expect(notify.error).not.toHaveBeenCalled();
  });
});
