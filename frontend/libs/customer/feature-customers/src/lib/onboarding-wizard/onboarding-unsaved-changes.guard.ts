import { CanDeactivateFn } from '@angular/router';
import type { CustomerOnboardingWizardComponent } from './customer-onboarding-wizard.component';

/**
 * Blocks navigation away from the onboarding wizard while any of its three
 * form groups is dirty, offering to save a draft first. Checked
 * synchronously at the moment navigation is attempted — reactive forms'
 * `dirty` flag needs no signal/valueChanges plumbing for a point-in-time
 * check like this.
 */
export const onboardingUnsavedChangesGuard: CanDeactivateFn<CustomerOnboardingWizardComponent> = (
  component,
) => component.confirmLeave();
