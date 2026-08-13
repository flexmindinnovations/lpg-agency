import { Route } from '@angular/router';

export const deliveryDriversRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./feature-drivers/feature-drivers').then((m) => m.FeatureDrivers),
  },
];
