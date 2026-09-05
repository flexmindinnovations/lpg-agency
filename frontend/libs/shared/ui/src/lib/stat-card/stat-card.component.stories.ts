import type { Meta, StoryObj } from '@storybook/angular';
import { StatCardComponent } from './stat-card.component';

const meta: Meta<StatCardComponent> = {
  title: 'Shared UI/Stat Card',
  component: StatCardComponent,
  decorators: [
    (story) => ({
      template: `<div style="max-inline-size: 300px;">${story().template}</div>`,
      ...story(),
    }),
  ],
  args: {
    label: 'Total Orders',
    value: '1,248',
    icon: 'pi pi-shopping-cart',
    tone: 'primary',
    delta: '+12.5%',
    caption: 'vs last week',
    trend: [8, 10, 9, 12, 11, 15, 14, 18],
    loading: false,
  },
};
export default meta;
type Story = StoryObj<StatCardComponent>;

export const Positive: Story = {};

export const Negative: Story = {
  args: { label: 'Pending', value: '214', icon: 'pi pi-clock', tone: 'warning', delta: '-3.1%', trend: [30, 26, 24, 25, 20, 18, 16, 14] },
};

export const NoTrend: Story = { args: { trend: [], delta: '', caption: 'All time' } };

export const Loading: Story = { args: { loading: true } };
