import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { provideRouter } from '@angular/router';
import { ProfileMenuComponent } from './profile-menu.component';

/**
 * A trivial host so the story can bind `email`/`role`/`collapsed` via args,
 * matching `app-shell`'s story pattern of wrapping rather than driving the
 * component directly.
 */
@Component({
  selector: 'lpg-profile-menu-story-host',
  standalone: true,
  imports: [ProfileMenuComponent],
  template: `
    <div style="inline-size: 18rem;">
      <lpg-profile-menu [email]="email" [role]="role" [collapsed]="collapsed" />
    </div>
  `,
})
class ProfileMenuStoryHost {
  @Input() email: string | null = 'david.taylor@novastack.dev';
  @Input() role = 'Branch Manager';
  @Input() collapsed = false;
}

const meta: Meta<ProfileMenuStoryHost> = {
  title: 'Shared UI/Profile Menu',
  component: ProfileMenuStoryHost,
  decorators: [
    applicationConfig({ providers: [provideRouter([])] }),
    moduleMetadata({ imports: [ProfileMenuComponent] }),
  ],
};

export default meta;
type Story = StoryObj<ProfileMenuStoryHost>;

export const Expanded: Story = {};

export const Collapsed: Story = {
  args: { collapsed: true },
};

export const NoEmailFallback: Story = {
  args: { email: null, role: 'Warehouse Staff' },
};
