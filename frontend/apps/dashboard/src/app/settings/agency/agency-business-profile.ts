import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { MessageService } from 'primeng/api';
import { FormFieldComponent, SectionCardComponent } from '@lpg/shared/ui';
import {
  AdminTenantService,
  type AgencyBusinessProfileResponse,
  type GstStateResponse,
  type TenantResponse,
} from '@lpg/shared/data-access';

/** 15 characters: state code, PAN, entity number, `Z`, check character.
 * The server also verifies the check character and the state match. */
const GSTIN_PATTERN = /^[0-9]{2}[A-Za-z]{5}[0-9]{4}[A-Za-z][1-9A-Za-z][Zz][0-9A-Za-z]$/;

/**
 * The agency's GST business profile (DA-13): legal name, address, state
 * and GSTIN printed as the supplier on every tax invoice. The state decides
 * CGST + SGST versus IGST.
 */
@Component({
  selector: 'lpg-agency-business-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    Select,
    FormFieldComponent,
    SectionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-section-card heading="GST and invoice details" class="profile-card">
      <p class="profile-lede">
        Printed as the supplier on every tax invoice. Invoices show “GSTIN: Not registered” until a
        GSTIN is entered.
      </p>
      <form [formGroup]="form" (ngSubmit)="save()" novalidate class="profile-form">
        <lpg-form-field
          label="Legal name"
          for="bp-legal-name"
          [control]="form.controls.legal_name"
          [messages]="{ required: 'Enter the registered business name.' }"
        >
          <input pInputText id="bp-legal-name" formControlName="legal_name" [fluid]="true" />
        </lpg-form-field>
        <lpg-form-field
          label="GSTIN"
          for="bp-gstin"
          [control]="form.controls.gstin"
          [optional]="true"
          hint="15 characters, e.g. 36AABCS1429B1ZV. Its first two digits must match the state."
          [messages]="{ pattern: 'A GSTIN is 15 characters, e.g. 36AABCS1429B1ZV.' }"
        >
          <input
            pInputText
            id="bp-gstin"
            formControlName="gstin"
            class="uppercase"
            [fluid]="true"
          />
        </lpg-form-field>
        <lpg-form-field
          label="Address line 1"
          for="bp-address-1"
          [control]="form.controls.address_line_1"
          [messages]="{ required: 'Enter the business address.' }"
        >
          <input pInputText id="bp-address-1" formControlName="address_line_1" [fluid]="true" />
        </lpg-form-field>
        <lpg-form-field
          label="Address line 2"
          for="bp-address-2"
          [control]="form.controls.address_line_2"
          [optional]="true"
        >
          <input pInputText id="bp-address-2" formControlName="address_line_2" [fluid]="true" />
        </lpg-form-field>
        <div class="profile-row">
          <lpg-form-field
            label="City"
            for="bp-city"
            [control]="form.controls.city"
            [messages]="{ required: 'Enter the city.' }"
          >
            <input pInputText id="bp-city" formControlName="city" [fluid]="true" />
          </lpg-form-field>
          <lpg-form-field
            label="PIN code"
            for="bp-pincode"
            [control]="form.controls.pincode"
            [messages]="{ required: 'Enter the PIN code.', pattern: 'A PIN code is 6 digits.' }"
          >
            <input
              pInputText
              id="bp-pincode"
              inputmode="numeric"
              formControlName="pincode"
              [fluid]="true"
            />
          </lpg-form-field>
        </div>
        <div class="profile-row">
          <lpg-form-field
            label="State"
            for="bp-state"
            [control]="form.controls.state_code"
            [messages]="{ required: 'Choose the state.' }"
          >
            <p-select
              inputId="bp-state"
              formControlName="state_code"
              [options]="states()"
              optionLabel="label"
              optionValue="code"
              [filter]="true"
              placeholder="Choose a state"
              appendTo="body"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="Phone"
            for="bp-phone"
            [control]="form.controls.phone"
            [optional]="true"
          >
            <input pInputText id="bp-phone" type="tel" formControlName="phone" [fluid]="true" />
          </lpg-form-field>
        </div>
        <div class="modal-actions">
          <button pButton type="submit" [disabled]="saving() || form.pristine">
            @if (saving()) {
              <i class="pi pi-spin pi-spinner"></i>
            }
            Save details
          </button>
        </div>
      </form>
    </lpg-section-card>
  `,
  styles: [
    `
      .profile-card {
        max-inline-size: 640px;
      }
      .profile-lede {
        margin: 0 0 var(--spacing-md);
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
      .profile-form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }
      .profile-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
        gap: var(--spacing-md);
      }
      .uppercase {
        text-transform: uppercase;
      }
    `,
  ],
})
export class AgencyBusinessProfile implements OnInit {
  private readonly tenantService = inject(AdminTenantService);
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(FormBuilder);

  readonly profile = input<AgencyBusinessProfileResponse | null>(null);
  readonly saved = output<TenantResponse>();

  protected readonly states = signal<(GstStateResponse & { label: string })[]>([]);
  protected readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    legal_name: ['', [Validators.required, Validators.maxLength(200)]],
    gstin: ['', Validators.pattern(GSTIN_PATTERN)],
    address_line_1: ['', [Validators.required, Validators.maxLength(200)]],
    address_line_2: ['', Validators.maxLength(200)],
    city: ['', [Validators.required, Validators.maxLength(100)]],
    state_code: ['', Validators.required],
    pincode: ['', [Validators.required, Validators.pattern(/^[1-9][0-9]{5}$/)]],
    phone: ['', Validators.maxLength(20)],
  });

  ngOnInit(): void {
    const current = this.profile();
    if (current) {
      this.form.reset({
        legal_name: current.legal_name,
        gstin: current.gstin ?? '',
        address_line_1: current.address_line_1,
        address_line_2: current.address_line_2 ?? '',
        city: current.city,
        state_code: current.state_code,
        pincode: current.pincode,
        phone: current.phone ?? '',
      });
    }
    this.tenantService.listGstStates().subscribe({
      next: (states) =>
        this.states.set(states.map((s) => ({ ...s, label: `${s.code} - ${s.name}` }))),
      error: () => this.states.set([]),
    });
  }

  protected save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.saving.set(true);
    this.tenantService
      .updateBusinessProfile({
        ...value,
        gstin: value.gstin.trim().toUpperCase() || null,
        address_line_2: value.address_line_2.trim() || null,
        phone: value.phone.trim() || null,
      })
      .subscribe({
        next: (tenant) => {
          this.saving.set(false);
          this.form.markAsPristine();
          this.saved.emit(tenant);
          this.messageService.add({
            severity: 'success',
            summary: 'Saved',
            detail: 'New invoices will print these details.',
          });
        },
        // Errors (e.g. a GSTIN check-digit mismatch) are toasted globally.
        error: () => this.saving.set(false),
      });
  }
}
