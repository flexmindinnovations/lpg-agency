import type { Meta, StoryObj } from '@storybook/angular';
import { SkeletonComponent } from './skeleton.component';

const meta: Meta<SkeletonComponent> = {
  title: 'Shared UI/Skeleton',
  component: SkeletonComponent,
  decorators: [
    (story) => ({
      template: `<div style="max-inline-size: 480px;">${story().template}</div>`,
      ...story(),
    }),
  ],
  args: { variant: 'block', width: '100%', height: '1rem', lines: 3, rows: 6, columns: 4 },
};
export default meta;
type Story = StoryObj<SkeletonComponent>;

export const Block: Story = { args: { width: '12rem', height: '2rem' } };
export const Text: Story = { args: { variant: 'text', lines: 4 } };
export const Circle: Story = { args: { variant: 'circle', width: '2.5rem', height: '2.5rem' } };
export const Table: Story = { args: { variant: 'table', rows: 5, columns: 5 } };
