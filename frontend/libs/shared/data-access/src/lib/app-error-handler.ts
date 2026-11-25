import { ErrorHandler, Injectable, inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { wasToasted } from './global-error-toast.interceptor';
import { errorMessageFor, isAppError } from './problem-details';
import { NotifyService } from './services/notify.service';

/** One message per burst: a render loop that throws on every change-detection
 * pass must not bury the screen in toasts. */
const MIN_INTERVAL_MS = 5000;

/**
 * App-wide handler for errors nothing else caught (a bug in a template, a
 * rejected promise, a failed lazy chunk, a failed request nobody subscribed an
 * error callback to). Replaces Angular's default, which only writes to the
 * console where the user never sees it.
 */
@Injectable()
export class AppErrorHandler implements ErrorHandler {
  private readonly notify = inject(NotifyService);
  private lastShownAt = 0;

  handleError(error: unknown): void {
    const apiError = isAppError(error) || error instanceof HttpErrorResponse;
    // A failed request nothing else reported (a lookup list loading in the
    // background, say) is shown here; one the interceptor already toasted is not.
    if (apiError && (wasToasted(error) || (error as { status?: number }).status === 401)) {
      return; // 401: the session-expired dialog already handles it.
    }
    // A screen reached into a module that is switched off. That is how the
    // agency is set up, not a fault to report: screens hide such parts, and one
    // that misses a call just goes without the data. A change the user asked
    // for is still explained, by the toast interceptor.
    if (isAppError(error) && error.errorCode === 'MODULE_DISABLED') {
      return;
    }
    const now = Date.now();
    if (now - this.lastShownAt < MIN_INTERVAL_MS) {
      return;
    }
    this.lastShownAt = now;
    this.notify.error(
      apiError
        ? errorMessageFor(error)
        : 'Something went wrong on this screen. Try again, or refresh the page if it keeps happening.',
    );
  }
}
