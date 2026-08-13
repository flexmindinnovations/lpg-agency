import { Route } from '@angular/router';

export const deliveryVehiclesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-vehicles/feature-vehicles').then((m) => m.FeatureVehicles),
  },
];
