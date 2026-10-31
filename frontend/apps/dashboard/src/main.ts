import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

/** Startup failed before Angular could render anything, so show the user a
 * plain message instead of a blank page. */
function showStartupError(): void {
  const banner = document.createElement('div');
  banner.setAttribute('role', 'alert');
  banner.style.cssText =
    'margin:2rem auto;max-width:32rem;padding:1rem 1.25rem;border:1px solid #f5c2c7;' +
    'border-radius:8px;background:#fff5f5;color:#842029;font:14px/1.5 sans-serif';
  banner.textContent =
    'The dashboard could not start. Refresh the page; if it keeps happening, contact support.';
  document.body.appendChild(banner);
}

bootstrapApplication(App, appConfig).catch(showStartupError);
