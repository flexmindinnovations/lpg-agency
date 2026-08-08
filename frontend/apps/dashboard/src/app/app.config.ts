import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { correlationIdInterceptor, problemDetailsInterceptor } from '@lpg/shared/data-access';
import { appRoutes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(appRoutes, withComponentInputBinding()),
    provideHttpClient(
      // Order matters: correlation ID is attached on the way out, Problem
      // Details are translated on the way back.
      withInterceptors([correlationIdInterceptor, problemDetailsInterceptor]),
    ),
  ],
};
