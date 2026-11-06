import type { DeviceStatus, LinkedDeviceResponse } from '@lpg/shared/data-access';
import type { ChipSeverity } from '@lpg/shared/ui';

/** Plain words for an agency admin, not the API's lowercase codes. */
export const STATUS_LABELS: Record<DeviceStatus, string> = {
  pending: 'Waiting',
  approved: 'Approved',
  blocked: 'Blocked',
  removed: 'Removed',
};

export const STATUS_SEVERITY: Record<DeviceStatus, ChipSeverity> = {
  pending: 'warn',
  approved: 'success',
  blocked: 'danger',
  removed: 'secondary',
};

export const APP_LABELS: Record<string, string> = {
  driver_app: 'Driver app',
  admin_app: 'Admin app',
};

export type DeviceControlMode = 'off' | 'observe' | 'enforce';

export const CONTROL_MODES: readonly {
  readonly value: DeviceControlMode;
  readonly label: string;
  readonly icon: string;
  readonly help: string;
}[] = [
  {
    value: 'off',
    label: 'Off',
    icon: 'pi pi-power-off',
    help: 'Any phone can use the Driver and Admin apps. Nothing is recorded.',
  },
  {
    value: 'observe',
    label: 'Watch only',
    icon: 'pi pi-eye',
    help: 'Phones are listed here as they sign in, and nobody is blocked. Use this first to build your list.',
  },
  {
    value: 'enforce',
    label: 'Approve phones',
    icon: 'pi pi-shield',
    help: 'Only approved phones can use the apps. A new phone waits here until you approve it, and a blocked phone is signed out.',
  },
];

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as DeviceStatus] ?? status;
}

export function statusSeverity(status: string): ChipSeverity {
  return STATUS_SEVERITY[status as DeviceStatus] ?? 'secondary';
}

export function appLabel(appType: string): string {
  return APP_LABELS[appType] ?? appType;
}

/** "Xiaomi Redmi 12" — the model without repeating the maker when the model
 * already starts with it. */
export function phoneModel(device: Pick<LinkedDeviceResponse, 'manufacturer' | 'model'>): string {
  const maker = device.manufacturer?.trim() ?? '';
  const model = device.model?.trim() ?? '';
  if (!maker) return model || '—';
  if (!model) return maker;
  return model.toLowerCase().startsWith(maker.toLowerCase()) ? model : `${maker} ${model}`;
}

/** "Driver app 1.4.0" */
export function appWithVersion(
  device: Pick<LinkedDeviceResponse, 'app_type' | 'app_version'>,
): string {
  const app = appLabel(device.app_type);
  return device.app_version ? `${app} ${device.app_version}` : app;
}

/** "Android 13" or "—" */
export function osLabel(device: Pick<LinkedDeviceResponse, 'os_version' | 'platform'>): string {
  const os = device.os_version?.trim();
  if (!os) return '—';
  const platform = device.platform === 'ios' ? 'iOS' : '';
  return platform && !os.toLowerCase().includes('ios') ? `${platform} ${os}` : os;
}

/** What an admin can do to a phone in each state. */
export function allowedActions(
  status: string,
): readonly ('approve' | 'block' | 'unblock' | 'remove')[] {
  switch (status) {
    case 'pending':
      return ['approve', 'block', 'remove'];
    case 'approved':
      return ['block', 'remove'];
    case 'blocked':
      return ['unblock', 'remove'];
    default:
      return [];
  }
}

const HISTORY_VERBS: Record<string, string> = {
  registered: 'Asked to be approved',
  approved: 'Approved',
  blocked: 'Blocked',
  unblocked: 'Unblocked',
  removed: 'Removed',
  updated: 'Details changed',
};

export function historyVerb(action: string): string {
  return HISTORY_VERBS[action] ?? action;
}
