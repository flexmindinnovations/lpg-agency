import { Route } from '@angular/router';

export const ordersFeatureRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./order-queue/order-queue').then((m) => m.OrderQueue),
  },
  {
    path: ':id',
    loadComponent: () => import('./order-detail/order-detail').then((m) => m.OrderDetail),
  },
];
