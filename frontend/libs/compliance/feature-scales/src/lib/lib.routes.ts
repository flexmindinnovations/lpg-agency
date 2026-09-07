import { Route } from '@angular/router';

export const complianceScalesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./feature-scales/feature-scales').then((m) => m.FeatureScales),
  },
];
