import { InjectionToken, Signal } from '@angular/core';

export interface PermissionState {
  permissions?: {
    has(permission: string): boolean;
  } | null;
}

export const PERMISSION_CHECKER = new InjectionToken<Signal<PermissionState | undefined | null>>(
  'PERMISSION_CHECKER'
);
