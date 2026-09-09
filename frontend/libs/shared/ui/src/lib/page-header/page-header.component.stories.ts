import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { provideRouter } from '@angular/router';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { PageHeaderComponent } from './page-header.component';

@Component({
  selector: 'lpg-page-header-story-host',
  standalone: true,
  imports: [PageHeaderComponent, ButtonDirective, ButtonIcon, ButtonLabel],
  template: `
    <div style="max-inline-size: 720px;">
      <lpg-page-header [title]="title" [subtitle]="subtitle" [backLink]="backLink" [backLabel]="backLabel">
        @if (withActions) {
          <button pButton actions severity="secondary"><i pButtonIcon class="pi pi-download"></i><span pButtonLabel>Export</span></button>
          <button pButton actions><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>New order</span></button>
        }
      </lpg-page-header>
    </div>
  `,
})
class PageHeaderStoryHost {
  @Input() title = 'Agency Overview';
  @Input() subtitle = "Live summary of your agency's operational data across every module.";
  @Input() backLink: string | null = null;
  @Input() backLabel = 'Back';
  @Input() withActions = true;
}

const meta: Meta<PageHeaderStoryHost> = {
  title: 'Shared UI/Page Header',
  component: PageHeaderStoryHost,
  decorators: [
    applicationConfig({ providers: [provideRouter([])] }),
    moduleMetadata({ imports: [PageHeaderComponent, ButtonDirective, ButtonIcon, ButtonLabel] }),
  ],
};
export default meta;
type Story = StoryObj<PageHeaderStoryHost>;

export const Default: Story = {};
export const WithBackLink: Story = {
  args: { title: 'Order #ORD-1248', subtitle: '', backLink: '/orders', backLabel: 'All orders', withActions: false },
};
export const TitleOnly: Story = { args: { subtitle: '', withActions: false } };
