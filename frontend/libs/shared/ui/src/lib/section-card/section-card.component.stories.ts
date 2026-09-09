import type { Meta, StoryObj } from '@storybook/angular';
import { moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { ButtonDirective } from 'primeng/button';
import { SectionCardComponent } from './section-card.component';

@Component({
  selector: 'lpg-section-card-story-host',
  standalone: true,
  imports: [SectionCardComponent, ButtonDirective],
  template: `
    <div style="max-inline-size: 560px;">
      <lpg-section-card [heading]="heading" [hasHeaderActions]="withHeaderActions">
        @if (withHeaderActions) {
          <button pButton headerActions type="button" size="small" text><i class="pi pi-download"></i><span>Export</span></button>
        }
        <p style="margin: 0; color: var(--color-text-secondary);">
          Any section content — a chart, a list, a form group — sits here on the
          standard card surface.
        </p>
      </lpg-section-card>
    </div>
  `,
})
class SectionCardStoryHost {
  @Input() heading = 'Fleet Status';
  @Input() withHeaderActions = false;
}

const meta: Meta<SectionCardStoryHost> = {
  title: 'Shared UI/Section Card',
  component: SectionCardStoryHost,
  decorators: [moduleMetadata({ imports: [SectionCardComponent, ButtonDirective] })],
};
export default meta;
type Story = StoryObj<SectionCardStoryHost>;

export const Default: Story = {};
export const WithHeaderActions: Story = { args: { withHeaderActions: true } };
export const NoHeading: Story = { args: { heading: '' } };
