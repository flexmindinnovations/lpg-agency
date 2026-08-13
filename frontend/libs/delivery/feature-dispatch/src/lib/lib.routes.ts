import { Route } from '@angular/router';

export const deliveryDispatchRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./feature-dispatch/feature-dispatch').then((m) => m.FeatureDispatch),
  },
];
