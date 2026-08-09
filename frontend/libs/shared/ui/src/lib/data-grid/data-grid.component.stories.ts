import type { Meta, StoryObj } from '@storybook/angular';
import { DataGridComponent, type DataGridColumn } from './data-grid.component';

interface DemoRow {
  readonly id: string;
  readonly name: string;
  readonly quantity: number;
}

const columns: readonly DataGridColumn<DemoRow>[] = [
  { field: 'id', header: 'ID', width: 100 },
  { field: 'name', header: 'Name', flex: 1 },
  { field: 'quantity', header: 'Quantity', numeric: true, width: 120 },
];

const rows: readonly DemoRow[] = [
  { id: 'CYL-001', name: '14.2kg domestic cylinder', quantity: 42 },
  { id: 'CYL-002', name: '19kg commercial cylinder', quantity: 17 },
  { id: 'CYL-003', name: '5kg portable cylinder', quantity: 63 },
];

const meta: Meta<DataGridComponent<DemoRow>> = {
  title: 'Shared UI/Data Grid',
  component: DataGridComponent,
  // AG Grid sizes itself to its host's block-size, which is 100% by
  // default (data-grid.component.ts's own :host style) — without an
  // explicit container height here, the grid would render at 0px tall.
  decorators: [
    (story) => ({
      template: `<div style="block-size: 400px;">${story().template}</div>`,
      ...story(),
    }),
  ],
  args: {
    rows,
    columns,
    ariaLabel: 'Example cylinder inventory grid',
    selectionMode: 'none',
    loading: false,
  },
};

export default meta;
type Story = StoryObj<DataGridComponent<DemoRow>>;

export const Default: Story = {};

export const SingleSelection: Story = {
  args: { selectionMode: 'single' },
};

export const Loading: Story = {
  args: { loading: true },
};
