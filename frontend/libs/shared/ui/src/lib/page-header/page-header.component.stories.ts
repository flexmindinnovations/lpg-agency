import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component, Input } from '@angular/core';
import { provideRouter } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { PageHeaderComponent } from './page-header.component';

@Component({
  selector: 'lpg-page-header-story-host',
  standalone: true,
  imports: [PageHeaderComponent, ButtonDirective],
  template: `
    <div style="max-inline-size: 720px;">
      <lpg-page-header [title]="title" [subtitle]="subtitle" [backLink]="backLink" [backLabel]="backLabel">
        @if (withActions) {
          <button pButton actions severity="secondary"><i class="pi pi-download"></i><span>Export</span></button>
          <button pButton actions><i class="pi pi-plus"></i><span>New order</span></button>
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
    moduleMetadata({ imports: [PageHeaderComponent, ButtonDirective] }),
  ],
};
export default meta;
type Story = StoryObj<PageHeaderStoryHost>;

export const Default: Story = {};
export const WithBackLink: Story = {
  args: { title: 'Order #ORD-1248', subtitle: '', backLink: '/orders', backLabel: 'All orders', withActions: false },
};
export const TitleOnly: Story = { args: { subtitle: '', withActions: false } };
