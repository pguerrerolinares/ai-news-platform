import { ApplicationConfig, APP_INITIALIZER, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHighcharts } from 'highcharts-angular';
import { routes } from './app.routes';
import { mockApiInterceptor, MOCK_JWT } from './interceptors/mock-api.interceptor';

// Pre-set a mock JWT so the auth guard passes on every navigation.
function initMockAuth() {
  return () => {
    localStorage.setItem('ainews_token', MOCK_JWT);
  };
}

// Exports the same symbol as app.config.ts so fileReplacements works transparently.
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withViewTransitions()),
    provideHttpClient(withInterceptors([mockApiInterceptor])),
    provideAnimationsAsync(),
    provideHighcharts(),
    {
      provide: APP_INITIALIZER,
      useFactory: initMockAuth,
      multi: true,
    },
  ],
};
