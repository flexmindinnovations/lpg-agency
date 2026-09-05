import type { Meta, StoryObj } from '@storybook/angular';
import { LiveIndicatorComponent } from './live-indicator.component';

const meta: Meta<LiveIndicatorComponent> = {
  title: 'Shared UI/Live Indicator',
  component: LiveIndicatorComponent,
  args: { active: true, label: '', ariaLabel: 'Live' },
};
export default meta;
type Story = StoryObj<LiveIndicatorComponent>;

export const Active: Story = {};
export const WithLabel: Story = { args: { label: '32 active deliveries' } };
export const Inactive: Story = { args: { active: false, label: 'Offline' } };
