import { Route } from '@angular/router';
import { permissionGuard } from '@lpg/shared/data-access';
import { FeatureCustomers } from './feature-customers/feature-customers';

export const featureCustomersRoutes: Route[] = [
  { path: '', component: FeatureCustomers },
  { 
    path: 'new', 
    canActivate: [permissionGuard('customers:create')],
    loadComponent: () => import('./onboarding-wizard/customer-onboarding-wizard.component').then(m => m.CustomerOnboardingWizardComponent)
  }
];
