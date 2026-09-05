import type { Meta, StoryObj } from '@storybook/angular';
import { applicationConfig, moduleMetadata } from '@storybook/angular';
import { Component } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { FormFieldComponent } from './form-field.component';

@Component({
  selector: 'lpg-form-field-story-host',
  standalone: true,
  imports: [FormFieldComponent, ReactiveFormsModule, InputTextModule, SelectModule],
  template: `
    <div style="max-inline-size: 420px; display: flex; flex-direction: column; gap: 20px;">
      <lpg-form-field
        label="First name"
        for="sb-fn"
        [control]="name"
        [messages]="{ required: 'First name is required' }"
      >
        <input id="sb-fn" pInputText [formControl]="name" />
      </lpg-form-field>

      <lpg-form-field label="Email" for="sb-email" [control]="email" hint="We only use this for receipts.">
        <input id="sb-email" pInputText [formControl]="email" />
      </lpg-form-field>

      <lpg-form-field label="Role" for="sb-role" [control]="role">
        <p-select
          inputId="sb-role"
          [formControl]="role"
          [options]="roles"
          optionLabel="label"
          optionValue="value"
        />
      </lpg-form-field>
    </div>
  `,
})
class FormFieldStoryHost {
  name = new FormControl('', { validators: [Validators.required] });
  email = new FormControl('not-an-email', { validators: [Validators.email] });
  role = new FormControl(null, { validators: [Validators.required] });
  roles = [
    { label: 'Dispatcher', value: 'dispatcher' },
    { label: 'Manager', value: 'manager' },
  ];

  constructor() {
    this.name.markAsTouched();
    this.email.markAsTouched();
  }
}

const meta: Meta<FormFieldStoryHost> = {
  title: 'Shared UI/Form Field',
  component: FormFieldStoryHost,
  decorators: [
    applicationConfig({ providers: [provideAnimationsAsync()] }),
    moduleMetadata({ imports: [FormFieldComponent, ReactiveFormsModule, InputTextModule, SelectModule] }),
  ],
};
export default meta;
type Story = StoryObj<FormFieldStoryHost>;

export const States: Story = {};
