import { Route } from '@angular/router';

export const complianceComplianceCalendarRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-compliance-calendar/feature-compliance-calendar').then(
        (m) => m.FeatureComplianceCalendar,
      ),
  },
];
