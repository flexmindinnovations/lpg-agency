import { ApplicationRef } from '@angular/core';
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

/** The boot splash in index.html stays up until the app has rendered its first
 * route and is idle (session restored, first requests done), and for at least
 * this long since the page started loading, so a fast refresh still shows it
 * instead of flashing by. It fades out (opacity only), then is removed. */
const SPLASH_MIN_MS = 700;
const SPLASH_MAX_MS = 15000;

function hideSplash(): void {
  const splash = document.querySelector<HTMLElement>('.boot');
  if (!splash) return;
  splash.classList.add('boot--leaving');
  const remove = () => splash.remove();
  splash.addEventListener('transitionend', remove, { once: true });
  setTimeout(remove, 600); // reduced motion has no transition to wait for
}

bootstrapApplication(App, appConfig)
  .then(async (ref) => {
    // Never keep the splash up forever if something never settles.
    await Promise.race([
      ref.injector.get(ApplicationRef).whenStable(),
      new Promise((resolve) => setTimeout(resolve, SPLASH_MAX_MS)),
    ]);
    const shown = performance.now();
    if (shown < SPLASH_MIN_MS) {
      await new Promise((resolve) => setTimeout(resolve, SPLASH_MIN_MS - shown));
    }
    hideSplash();
  })
  .catch(() => {
    document.querySelector('.boot')?.remove();
    showStartupError();
  });
