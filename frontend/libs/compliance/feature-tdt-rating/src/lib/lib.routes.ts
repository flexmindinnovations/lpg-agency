import { Route } from '@angular/router';

export const complianceTdtRatingRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./tdt-rating-config/tdt-rating-config').then((m) => m.TdtRatingConfig),
  },
];
