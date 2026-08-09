import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component } from '@angular/core';
import { provideRouter } from '@angular/router';
import { AppShellComponent } from './app-shell.component';
import type { NavGroup } from './nav-item';

const navGroups: readonly NavGroup[] = [
  {
    items: [
      { label: 'Home', icon: 'pi pi-home', route: '/', exact: true },
      { label: 'Alerts', icon: 'pi pi-bell', route: '/alerts', badge: 3 },
    ],
  },
  {
    label: 'Example group',
    items: [{ label: 'Settings', icon: 'pi pi-cog', route: '/settings' }],
  },
];

/**
 * A trivial host so the story can bind `navGroups` and project real content
 * into `<lpg-app-shell>`, rather than trying to drive `AppShellComponent`
 * as if it were a leaf component with no content projection.
 */
@Component({
  selector: 'lpg-app-shell-story-host',
  standalone: true,
  imports: [AppShellComponent],
  template: `
    <lpg-app-shell brandName="LPG Agency" [navGroups]="navGroups">
      <p>Routed content renders here.</p>
    </lpg-app-shell>
  `,
})
class AppShellStoryHost {
  protected readonly navGroups = navGroups;
}

const meta: Meta<AppShellStoryHost> = {
  title: 'Shared UI/App Shell',
  component: AppShellStoryHost,
  decorators: [
    applicationConfig({ providers: [provideRouter([])] }),
    moduleMetadata({ imports: [AppShellComponent] }),
  ],
};

export default meta;
type Story = StoryObj<AppShellStoryHost>;

export const Default: Story = {};
