import { Route } from '@angular/router';
import { permissionGuard } from '@lpg/shared/data-access';
import { FeatureCustomers } from './feature-customers/feature-customers';
import { onboardingUnsavedChangesGuard } from './onboarding-wizard/onboarding-unsaved-changes.guard';

export const featureCustomersRoutes: Route[] = [
  { path: '', component: FeatureCustomers },
  {
    path: 'new',
    canActivate: [permissionGuard('customers:create')],
    canDeactivate: [onboardingUnsavedChangesGuard],
    loadComponent: () => import('./onboarding-wizard/customer-onboarding-wizard.component').then(m => m.CustomerOnboardingWizardComponent)
  }
];
