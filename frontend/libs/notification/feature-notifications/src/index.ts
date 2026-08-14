import { Route } from '@angular/router';
import { NotificationFeatureNotifications } from './lib/notification-feature-notifications/notification-feature-notifications';

export const notificationFeatureNotificationsRoutes: Route[] = [
  {
    path: '',
    component: NotificationFeatureNotifications,
  },
];

export * from './lib/notification-feature-notifications/notification-feature-notifications';
export * from './lib/notification-bell';
export * from './lib/notification-drawer';