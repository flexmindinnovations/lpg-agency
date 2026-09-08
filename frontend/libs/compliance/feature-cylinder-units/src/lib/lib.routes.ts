import { Route } from '@angular/router';

export const complianceCylinderUnitsRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-cylinder-units/feature-cylinder-units').then(
        (m) => m.FeatureCylinderUnits,
      ),
  },
];
