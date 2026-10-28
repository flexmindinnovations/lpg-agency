import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Textarea } from 'primeng/textarea';
import { MessageService } from 'primeng/api';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { FormFieldComponent, PageHeaderComponent, SectionCardComponent } from '@lpg/shared/ui';
import { PaymentProfileService, type PaymentProfileResponse } from '@lpg/shared/data-access';

const IFSC_PATTERN = /^[A-Za-z]{4}0[A-Za-z0-9]{6}$/;
const ACCOUNT_PATTERN = /^[0-9 ]{9,22}$/;
const UPI_PATTERN = /^[a-zA-Z0-9._-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$/;

/**
 * Where customers pay the agency (ADR-066): bank account and UPI ID. They
 * are printed in the "How to pay" block of every invoice, and the UPI ID
 * drives the pay QR shown on the dashboard and in the Driver and Customer
 * apps.
 */
@Component({
  selector: 'lpg-payment-settings',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    Textarea,
    FormFieldComponent,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    SectionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-template lpgHeaderTitlePortal>
      <lpg-page-header
        title="Payments"
        subtitle="Bank and UPI details printed on invoices and used for pay QR codes."
      />
    </ng-template>

    <form [formGroup]="form" (ngSubmit)="save()" novalidate class="payments">
      <lpg-section-card heading="Bank account" class="payments__card">
        <p class="payments__lede">
          Shown on invoices so customers can pay by NEFT, RTGS or IMPS. Leave all three required
          fields blank to hide the bank block.
        </p>
        <div class="payments__grid">
          <lpg-form-field
            label="Account holder"
            for="pp-holder"
            [control]="form.controls.account_holder"
            [optional]="true"
          >
            <input pInputText id="pp-holder" formControlName="account_holder" [fluid]="true" />
          </lpg-form-field>
          <lpg-form-field
            label="Bank"
            for="pp-bank"
            [control]="form.controls.bank_name"
            [optional]="true"
          >
            <input pInputText id="pp-bank" formControlName="bank_name" [fluid]="true" />
          </lpg-form-field>
          <lpg-form-field
            label="Account number"
            for="pp-account"
            [control]="form.controls.account_number"
            [optional]="true"
            [messages]="{ pattern: 'An account number is 9 to 18 digits.' }"
          >
            <input
              pInputText
              id="pp-account"
              inputmode="numeric"
              formControlName="account_number"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="IFSC"
            for="pp-ifsc"
            [control]="form.controls.ifsc"
            [optional]="true"
            hint="11 characters, e.g. HDFC0001234."
            [messages]="{ pattern: 'An IFSC is 11 characters, e.g. HDFC0001234.' }"
          >
            <input
              pInputText
              id="pp-ifsc"
              class="payments__upper"
              formControlName="ifsc"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="Branch"
            for="pp-branch"
            [control]="form.controls.branch"
            [optional]="true"
          >
            <input pInputText id="pp-branch" formControlName="branch" [fluid]="true" />
          </lpg-form-field>
        </div>
      </lpg-section-card>

      <lpg-section-card heading="UPI" class="payments__card">
        <p class="payments__lede">
          Customers scan the QR with any UPI app (PhonePe, Google Pay, Paytm, BHIM). The amount is
          filled in for them.
        </p>
        <div class="payments__grid">
          <lpg-form-field
            label="UPI ID"
            for="pp-upi"
            [control]="form.controls.upi_id"
            [optional]="true"
            hint="Like name@okhdfcbank."
            [messages]="{ pattern: 'A UPI ID looks like name@bank.' }"
          >
            <input pInputText id="pp-upi" formControlName="upi_id" [fluid]="true" />
          </lpg-form-field>
          <lpg-form-field
            label="Name shown to the payer"
            for="pp-payee"
            [control]="form.controls.upi_payee_name"
            [optional]="true"
            hint="Defaults to the account holder."
          >
            <input pInputText id="pp-payee" formControlName="upi_payee_name" [fluid]="true" />
          </lpg-form-field>
        </div>
      </lpg-section-card>

      <lpg-section-card heading="Invoice footer" class="payments__card">
        <lpg-form-field
          label="Note printed at the bottom of every invoice"
          for="pp-footer"
          [control]="form.controls.invoice_footer_note"
          [optional]="true"
          hint="For example payment terms or a thank-you line."
        >
          <textarea
            pTextarea
            id="pp-footer"
            rows="2"
            formControlName="invoice_footer_note"
            [fluid]="true"
          ></textarea>
        </lpg-form-field>
      </lpg-section-card>

      <div class="modal-actions">
        <button pButton type="submit" [disabled]="saving() || form.pristine">
          @if (saving()) {
            <i class="pi pi-spin pi-spinner"></i>
          }
          Save payment details
        </button>
      </div>
    </form>
  `,
  styles: [
    `
      .payments {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding-block-end: var(--spacing-xl);
      }
      .payments__card {
        inline-size: 100%;
        max-inline-size: none;
      }
      .payments__lede {
        margin: 0 0 var(--spacing-md);
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
      .payments__grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
        gap: var(--spacing-md);
      }
      .payments__upper {
        text-transform: uppercase;
      }
    `,
  ],
})
export class PaymentSettings implements OnInit {
  private readonly service = inject(PaymentProfileService);
  private readonly messages = inject(MessageService);
  private readonly fb = inject(FormBuilder);

  protected readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    account_holder: ['', Validators.maxLength(120)],
    bank_name: ['', Validators.maxLength(120)],
    account_number: ['', Validators.pattern(ACCOUNT_PATTERN)],
    ifsc: ['', Validators.pattern(IFSC_PATTERN)],
    branch: ['', Validators.maxLength(120)],
    upi_id: ['', Validators.pattern(UPI_PATTERN)],
    upi_payee_name: ['', Validators.maxLength(100)],
    invoice_footer_note: ['', Validators.maxLength(300)],
  });

  ngOnInit(): void {
    this.service.get().subscribe({
      next: (profile) => this.fill(profile),
      error: () => undefined,
    });
  }

  protected save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.service.save(this.form.getRawValue()).subscribe({
      next: (profile) => {
        this.saving.set(false);
        this.fill(profile);
        this.messages.add({
          severity: 'success',
          summary: 'Saved',
          detail: 'New invoices and pay QR codes use these details.',
        });
      },
      // Validation messages (half-filled bank block, missing payee name) are toasted globally.
      error: () => this.saving.set(false),
    });
  }

  private fill(profile: PaymentProfileResponse): void {
    this.form.reset({
      account_holder: profile.account_holder ?? '',
      bank_name: profile.bank_name ?? '',
      account_number: profile.account_number ?? '',
      ifsc: profile.ifsc ?? '',
      branch: profile.branch ?? '',
      upi_id: profile.upi_id ?? '',
      upi_payee_name: profile.upi_payee_name ?? '',
      invoice_footer_note: profile.invoice_footer_note ?? '',
    });
  }
}
