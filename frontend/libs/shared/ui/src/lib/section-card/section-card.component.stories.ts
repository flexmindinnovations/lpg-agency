import type { Meta, StoryObj } from '@storybook/angular';
import { moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { SectionCardComponent } from './section-card.component';

@Component({
  selector: 'lpg-section-card-story-host',
  standalone: true,
  imports: [SectionCardComponent, ButtonModule],
  template: `
    <div style="max-inline-size: 560px;">
      <lpg-section-card [heading]="heading" [hasHeaderActions]="withHeaderActions">
        @if (withHeaderActions) {
          <p-button headerActions label="Export" size="small" [text]="true" icon="pi pi-download" />
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
  decorators: [moduleMetadata({ imports: [SectionCardComponent, ButtonModule] })],
};
export default meta;
type Story = StoryObj<SectionCardStoryHost>;

export const Default: Story = {};
export const WithHeaderActions: Story = { args: { withHeaderActions: true } };
export const NoHeading: Story = { args: { heading: '' } };
