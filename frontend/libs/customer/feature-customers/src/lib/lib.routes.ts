import { Route } from '@angular/router';
import { FeatureCustomers } from './feature-customers/feature-customers';

export const featureCustomersRoutes: Route[] = [
  { path: '', component: FeatureCustomers },
  { 
    path: 'new', 
    loadComponent: () => import('./onboarding-wizard/customer-onboarding-wizard.component').then(m => m.CustomerOnboardingWizardComponent)
  }
];
