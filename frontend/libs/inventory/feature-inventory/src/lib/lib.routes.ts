import { Route } from '@angular/router';

export const inventoryFeatureRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-inventory/feature-inventory').then((m) => m.FeatureInventory),
  },
];
