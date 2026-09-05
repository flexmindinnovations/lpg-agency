import type { Meta, StoryObj } from '@storybook/angular';
import { ActivityListComponent, type ActivityItem } from './activity-list.component';

const items: ActivityItem[] = [
  { time: '2m ago', icon: 'pi pi-check-circle', title: 'Order #ORD-1248', description: 'Delivered successfully', status: 'Delivered', statusTone: 'success' },
  { time: '15m ago', icon: 'pi pi-wallet', title: 'Payment received', description: '₹45,000 from HP Gas', status: 'Paid', statusTone: 'success' },
  { time: '30m ago', icon: 'pi pi-plus-circle', title: 'New order received', description: 'Order #ORD-1249' },
  { time: '1h ago', icon: 'pi pi-exclamation-triangle', title: 'Low stock alert', description: 'Indane 14.2kg — 120 left', status: 'Warning', statusTone: 'warning' },
];

const meta: Meta<ActivityListComponent> = {
  title: 'Shared UI/Activity List',
  component: ActivityListComponent,
  decorators: [
    (story) => ({
      template: `<div style="max-inline-size: 440px;">${story().template}</div>`,
      ...story(),
    }),
  ],
  args: { items },
};
export default meta;
type Story = StoryObj<ActivityListComponent>;

export const Default: Story = {};
export const Empty: Story = { args: { items: [] } };
