import type { NavItem } from '@lpg/shared/ui/app-shell';

/** A Settings destination. `permission` mirrors the route's `permissionGuard`
 * so the nav never offers a section the router would refuse. */
export interface SettingsSection extends NavItem {
  readonly permission?: string;
}

export interface SettingsGroup {
  readonly label: string;
  readonly sections: readonly SettingsSection[];
}

/** Account is personal (every role); Agency is tenant-wide administration. */
export const SETTINGS_GROUPS: readonly SettingsGroup[] = [
  {
    label: 'Account',
    sections: [{ label: 'My Profile', icon: 'pi pi-user', route: '/settings/account' }],
  },
  {
    label: 'Agency',
    sections: [
      {
        label: 'Agency',
        icon: 'pi pi-building',
        route: '/settings/agency',
        permission: 'tenant:read',
      },
      {
        label: 'Configuration',
        icon: 'pi pi-cog',
        route: '/settings/configuration',
        permission: 'tenant:configure',
      },
      {
        label: 'Feature Flags',
        icon: 'pi pi-flag',
        route: '/settings/feature-flags',
        permission: 'feature_flags:manage_tenant',
      },
      {
        label: 'License',
        icon: 'pi pi-key',
        route: '/settings/license',
        exact: true,
        permission: 'license:manage_tenant',
      },
      {
        label: 'Linked Devices',
        icon: 'pi pi-mobile',
        route: '/settings/license/devices',
        permission: 'license:manage_tenant',
      },
    ],
  },
];

/** The groups (and sections within them) the given permission check allows;
 * groups left empty are dropped. */
export function visibleSettingsGroups(can: (code: string) => boolean): SettingsGroup[] {
  return SETTINGS_GROUPS.map((group) => ({
    label: group.label,
    sections: group.sections.filter((s) => !s.permission || can(s.permission)),
  })).filter((group) => group.sections.length > 0);
}
