import { Route } from '@angular/router';
import { FeatureInvoices } from './feature-invoices/feature-invoices';

export const featureInvoicesRoutes: Route[] = [{ path: '', component: FeatureInvoices }];

/** DA-33: mounted at `/cash-handovers` by the dashboard app. */
export const cashHandoverRegisterRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./cash-handover-register/cash-handover-register').then((m) => m.CashHandoverRegister),
  },
];
