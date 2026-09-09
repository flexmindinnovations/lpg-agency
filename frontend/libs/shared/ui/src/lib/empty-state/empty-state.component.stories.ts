import type { Meta, StoryObj } from '@storybook/angular';
import { moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { ButtonDirective } from 'primeng/button';
import { EmptyStateComponent, type EmptyStateTone } from './empty-state.component';

@Component({
  selector: 'lpg-empty-state-story-host',
  standalone: true,
  imports: [EmptyStateComponent, ButtonDirective],
  template: `
    <div style="max-inline-size: 480px;">
      <lpg-empty-state [title]="title" [description]="description" [tone]="tone" [icon]="icon">
        @if (withAction) {
          <button
            pButton
            actions
            type="button"
            [severity]="tone === 'error' ? 'secondary' : undefined"
          ><span>{{ tone === 'error' ? 'Retry' : 'Schedule delivery' }}</span></button>
        }
      </lpg-empty-state>
    </div>
  `,
})
class EmptyStateStoryHost {
  @Input() title = 'No deliveries scheduled';
  @Input() description = 'There are no deliveries for this date.';
  @Input() tone: EmptyStateTone = 'neutral';
  @Input() icon = '';
  @Input() withAction = true;
}

const meta: Meta<EmptyStateStoryHost> = {
  title: 'Shared UI/Empty State',
  component: EmptyStateStoryHost,
  decorators: [moduleMetadata({ imports: [EmptyStateComponent, ButtonDirective] })],
};
export default meta;
type Story = StoryObj<EmptyStateStoryHost>;

export const Neutral: Story = {};

export const Error: Story = {
  args: {
    tone: 'error',
    title: 'Unable to load orders',
    description: "We couldn't retrieve your order data. Check your connection and try again.",
  },
};

export const NoAction: Story = { args: { withAction: false } };
