import { Route } from '@angular/router';

export const reportingFeatureReportsRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./reports-layout/reports-layout').then((m) => m.ReportsLayout),
    children: [
      {
        path: '',
        pathMatch: 'full',
        redirectTo: 'daily-sales',
      },
      {
        path: 'daily-sales',
        loadComponent: () =>
          import('./daily-sales/daily-sales').then((m) => m.DailySales),
      },
      {
        path: 'driver-performance',
        loadComponent: () =>
          import('./driver-performance/driver-performance').then(
            (m) => m.DriverPerformance
          ),
      },
      {
        path: 'customer-consumption',
        loadComponent: () =>
          import('./customer-consumption/customer-consumption').then(
            (m) => m.CustomerConsumption
          ),
      },
      {
        path: 'gst-filing',
        loadComponent: () =>
          import('./gst-filing/gst-filing').then((m) => m.GstFiling),
      },
    ],
  },
];
