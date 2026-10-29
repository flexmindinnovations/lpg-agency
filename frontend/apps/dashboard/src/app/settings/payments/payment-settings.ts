import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { map, startWith } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Textarea } from 'primeng/textarea';
import { MessageService } from 'primeng/api';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  FormFieldComponent,
  PageHeaderComponent,
  SectionCardComponent,
  UpiAppsComponent,
} from '@lpg/shared/ui';
import {
  PaymentProfileService,
  type IfscCheckResponse,
  type PaymentProfileResponse,
  type UpiCheckResponse,
} from '@lpg/shared/data-access';

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
    UpiAppsComponent,
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
          @if (confirmNeeded()) {
            <lpg-form-field
              label="Confirm account number"
              for="pp-account-confirm"
              [control]="form.controls.account_number_confirm"
              hint="Type it again so a typo does not end up on every invoice."
              [messages]="{ mismatch: 'The two account numbers do not match.' }"
            >
              <input
                pInputText
                id="pp-account-confirm"
                inputmode="numeric"
                autocomplete="off"
                formControlName="account_number_confirm"
                [fluid]="true"
              />
            </lpg-form-field>
          }
          <lpg-form-field
            label="IFSC"
            for="pp-ifsc"
            [control]="form.controls.ifsc"
            [optional]="true"
            hint="11 characters, e.g. HDFC0001234."
            [messages]="{
              pattern: 'An IFSC is 11 characters, e.g. HDFC0001234.',
              notFound: 'No bank branch has this IFSC. Check your cheque book or passbook.',
            }"
          >
            <input
              pInputText
              id="pp-ifsc"
              class="payments__upper"
              formControlName="ifsc"
              [fluid]="true"
              (blur)="verifyIfsc()"
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
        <div class="payments__check" aria-live="polite">
          <button
            pButton
            type="button"
            size="small"
            severity="secondary"
            [outlined]="true"
            [disabled]="checking() === 'ifsc'"
            (click)="verifyIfsc()"
          >
            @if (checking() === 'ifsc') {
              <i class="pi pi-spin pi-spinner"></i>
            }
            Verify IFSC
          </button>
          @if (ifscCheck(); as check) {
            @if (check.status === 'verified') {
              <span class="payments__result payments__result--ok">
                <i class="pi pi-check-circle" aria-hidden="true"></i>
                {{ bankSummary(check) }}
              </span>
            } @else if (check.status === 'unavailable') {
              <span class="payments__result payments__result--warn">
                <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
                The bank directory could not be reached. The code looks right, and you can still
                save.
              </span>
            }
          }
        </div>
      </lpg-section-card>

      <lpg-section-card heading="UPI" class="payments__card">
        <p class="payments__lede">
          Customers scan the QR with any UPI app (PhonePe, Google Pay, Paytm, BHIM). The amount is
          filled in for them.
        </p>
        <lpg-upi-apps class="payments__apps" />
        <div class="payments__grid">
          <lpg-form-field
            label="UPI ID"
            for="pp-upi"
            [control]="form.controls.upi_id"
            [optional]="true"
            hint="Like name@okhdfcbank."
            [messages]="{ pattern: 'A UPI ID looks like name@bank.' }"
          >
            <input
              pInputText
              id="pp-upi"
              formControlName="upi_id"
              autocapitalize="none"
              spellcheck="false"
              [fluid]="true"
              (blur)="verifyUpi()"
            />
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
        <div class="payments__check" aria-live="polite">
          <button
            pButton
            type="button"
            size="small"
            severity="secondary"
            [outlined]="true"
            [disabled]="checking() === 'upi'"
            (click)="verifyUpi()"
          >
            @if (checking() === 'upi') {
              <i class="pi pi-spin pi-spinner"></i>
            }
            Verify UPI ID
          </button>
          @if (upiCheck(); as check) {
            @if (check.handle_known) {
              <span class="payments__result payments__result--ok">
                <i class="pi pi-check-circle" aria-hidden="true"></i>
                Valid format. &#64;{{ check.handle }} is issued by {{ check.provider }}.
              </span>
            } @else {
              <span class="payments__result payments__result--warn">
                <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
                Valid format, but &#64;{{ check.handle }} is not a handle we recognise. Check the
                spelling.
              </span>
            }
          }
        </div>
        <p class="payments__note">
          This checks the format and the bank or app behind the ID. To confirm the ID is yours, scan
          the QR from another UPI app once — the name it shows is the one customers will see.
        </p>
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
      .payments__apps {
        margin-block-end: var(--spacing-md);
      }
      .payments__check {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-md);
      }
      .payments__result {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        font-size: var(--typography-body-small-font-size);
      }
      .payments__result--ok {
        color: var(--color-status-success);
      }
      .payments__result--warn {
        color: var(--color-status-warning);
      }
      .payments__note {
        margin: var(--spacing-md) 0 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
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
  protected readonly checking = signal<'ifsc' | 'upi' | null>(null);
  protected readonly ifscCheck = signal<IfscCheckResponse | null>(null);
  protected readonly upiCheck = signal<UpiCheckResponse | null>(null);

  /** The account number as last saved: only a changed one needs typing twice. */
  private savedAccount = '';

  readonly form = this.fb.nonNullable.group({
    account_holder: ['', Validators.maxLength(120)],
    bank_name: ['', Validators.maxLength(120)],
    account_number: ['', Validators.pattern(ACCOUNT_PATTERN)],
    account_number_confirm: ['', (control: AbstractControl) => this.confirmMatches(control)],
    ifsc: ['', Validators.pattern(IFSC_PATTERN)],
    branch: ['', Validators.maxLength(120)],
    upi_id: ['', Validators.pattern(UPI_PATTERN)],
    upi_payee_name: ['', Validators.maxLength(100)],
    invoice_footer_note: ['', Validators.maxLength(300)],
  });

  private readonly accountNumber = toSignal(
    this.form.controls.account_number.valueChanges.pipe(
      startWith(this.form.controls.account_number.value),
      map((value) => this.digitsOnly(value)),
    ),
    { initialValue: '' },
  );

  protected readonly confirmNeeded = computed(() => {
    const account = this.accountNumber();
    return account !== '' && account !== this.savedAccount;
  });

  ngOnInit(): void {
    this.form.controls.account_number.valueChanges.subscribe(() =>
      this.form.controls.account_number_confirm.updateValueAndValidity(),
    );
    this.form.controls.ifsc.valueChanges.subscribe(() => this.ifscCheck.set(null));
    this.form.controls.upi_id.valueChanges.subscribe(() => this.upiCheck.set(null));
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
    const { account_number_confirm: _confirm, ...profile } = this.form.getRawValue();
    this.service.save(profile).subscribe({
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

  protected verifyIfsc(): void {
    const control = this.form.controls.ifsc;
    const ifsc = control.value.trim().toUpperCase();
    if (!ifsc || !IFSC_PATTERN.test(ifsc) || this.checking()) return;
    this.checking.set('ifsc');
    this.service.verify({ ifsc }).subscribe({
      next: ({ ifsc: check }) => {
        this.checking.set(null);
        if (!check) return;
        this.ifscCheck.set(check);
        if (check.status === 'not_found') {
          control.setErrors({ ...control.errors, notFound: true });
          control.markAsTouched();
        } else if (check.status === 'verified') {
          this.fillFromBranch(check);
        }
      },
      error: () => this.checking.set(null),
    });
  }

  protected verifyUpi(): void {
    const upiId = this.form.controls.upi_id.value.trim().toLowerCase();
    if (!upiId || !UPI_PATTERN.test(upiId) || this.checking()) return;
    this.checking.set('upi');
    this.service.verify({ upi_id: upiId }).subscribe({
      next: ({ upi }) => {
        this.checking.set(null);
        this.upiCheck.set(upi ?? null);
      },
      error: () => this.checking.set(null),
    });
  }

  protected bankSummary(check: IfscCheckResponse): string {
    const place = [check.branch, check.city].filter(Boolean).join(', ');
    return [check.bank, place].filter(Boolean).join(' · ');
  }

  /** Fills bank and branch only where they are still blank, so a name the
   * agency typed itself is never overwritten. */
  private fillFromBranch(check: IfscCheckResponse): void {
    const { bank_name, branch } = this.form.controls;
    if (!bank_name.value && check.bank) bank_name.setValue(check.bank);
    if (!branch.value && check.branch) branch.setValue(check.branch);
    if (bank_name.dirty || branch.dirty) this.form.markAsDirty();
  }

  private confirmMatches(control: AbstractControl): ValidationErrors | null {
    const account = this.digitsOnly(control.parent?.get('account_number')?.value);
    if (!account || account === this.savedAccount) return null;
    return this.digitsOnly(control.value) === account ? null : { mismatch: true };
  }

  private digitsOnly(value: unknown): string {
    return String(value ?? '').replace(/\s+/g, '');
  }

  private fill(profile: PaymentProfileResponse): void {
    this.savedAccount = profile.account_number ?? '';
    this.ifscCheck.set(null);
    this.upiCheck.set(null);
    this.form.reset({
      account_holder: profile.account_holder ?? '',
      bank_name: profile.bank_name ?? '',
      account_number: profile.account_number ?? '',
      account_number_confirm: '',
      ifsc: profile.ifsc ?? '',
      branch: profile.branch ?? '',
      upi_id: profile.upi_id ?? '',
      upi_payee_name: profile.upi_payee_name ?? '',
      invoice_footer_note: profile.invoice_footer_note ?? '',
    });
  }
}
