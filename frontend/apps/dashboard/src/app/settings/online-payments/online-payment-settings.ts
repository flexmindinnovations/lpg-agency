import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { ConfirmationService, MessageService } from 'primeng/api';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { FormFieldComponent, PageHeaderComponent, SectionCardComponent } from '@lpg/shared/ui';
import {
  PaymentGatewayService,
  type PaymentGatewaySettingsResponse,
} from '@lpg/shared/data-access';

const KEY_ID_PATTERN = /^\s*rzp_(test|live)_[A-Za-z0-9]{6,40}\s*$/;

/**
 * The agency's own Razorpay account (ADR-067). Each agency collects online
 * payments into its own account, so the key, key secret and webhook secret
 * are entered here rather than set on the server. Secrets are write-only: once
 * saved they are never shown again, only "saved".
 */
@Component({
  selector: 'lpg-online-payment-settings',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    Message,
    FormFieldComponent,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    SectionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-template lpgHeaderTitlePortal>
      <lpg-page-header
        title="Online Payments"
        subtitle="Your Razorpay account for payment links in the apps, on WhatsApp and for staff."
      />
    </ng-template>

    <div class="gateway">
      @if (settings(); as current) {
        @switch (current.source) {
          @case ('agency') {
            <p-message [severity]="current.mode === 'live' ? 'success' : 'warn'">
              @if (current.mode === 'live') {
                Live mode. Customers' payments go to your Razorpay account.
              } @else {
                Test mode. Razorpay test keys never move real money — switch to your live key before
                taking real payments.
              }
            </p-message>
          }
          @case ('platform') {
            <p-message severity="info">
              No key saved. Payments go through the platform's shared Razorpay account. Save your
              own key below to collect into your account instead.
            </p-message>
          }
          @case ('demo') {
            <p-message severity="info">
              This server is running the demo gateway, so no real money moves. Save your own
              Razorpay key below to take real payments.
            </p-message>
          }
          @default {
            <p-message severity="warn">
              Online payment is off. Save your Razorpay key below to let customers pay by link.
            </p-message>
          }
        }
      }

      <form [formGroup]="form" (ngSubmit)="save()" novalidate>
        <lpg-section-card heading="Razorpay keys" class="gateway__card">
          <p class="gateway__lede">
            In Razorpay, open <strong>Account &amp; Settings &rarr; API Keys</strong> and generate a
            key. Razorpay shows the secret once, so copy it straight into the field below.
          </p>
          <div class="gateway__grid">
            <lpg-form-field
              label="Key id"
              for="pg-key-id"
              [control]="form.controls.key_id"
              [hint]="
                settings()?.configured
                  ? 'Saved as ' + settings()?.key_id_masked + '. Leave blank to keep it.'
                  : 'Starts with rzp_live_ or rzp_test_.'
              "
              [messages]="{ pattern: 'A key id looks like rzp_live_… or rzp_test_….' }"
            >
              <input
                pInputText
                id="pg-key-id"
                formControlName="key_id"
                autocomplete="off"
                autocapitalize="none"
                spellcheck="false"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="Key secret"
              for="pg-key-secret"
              [control]="form.controls.key_secret"
              [optional]="settings()?.has_key_secret ?? false"
              [hint]="
                settings()?.has_key_secret
                  ? 'Saved. Leave blank to keep it.'
                  : 'Paste the secret Razorpay showed you.'
              "
            >
              <input
                pInputText
                id="pg-key-secret"
                type="password"
                formControlName="key_secret"
                autocomplete="new-password"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="Webhook secret"
              for="pg-webhook-secret"
              [control]="form.controls.webhook_secret"
              [optional]="true"
              [hint]="
                settings()?.has_webhook_secret
                  ? 'Saved. Leave blank to keep it.'
                  : 'Needed for payments to update automatically. Use the same text as in the webhook below.'
              "
            >
              <input
                pInputText
                id="pg-webhook-secret"
                type="password"
                formControlName="webhook_secret"
                autocomplete="new-password"
                [fluid]="true"
              />
            </lpg-form-field>
          </div>
          @if (testResult(); as result) {
            <p-message [severity]="result.ok ? 'success' : 'error'">{{ result.message }}</p-message>
          }
          <div class="modal-actions">
            @if (settings()?.configured) {
              <button
                pButton
                type="button"
                severity="secondary"
                [outlined]="true"
                [disabled]="testing()"
                (click)="test()"
              >
                @if (testing()) {
                  <i class="pi pi-spin pi-spinner"></i>
                }
                Test connection
              </button>
              <button
                pButton
                type="button"
                severity="danger"
                [text]="true"
                (click)="confirmRemove()"
              >
                Remove keys
              </button>
            }
            <button pButton type="submit" [disabled]="saving() || form.pristine">
              @if (saving()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save keys
            </button>
          </div>
        </lpg-section-card>
      </form>

      @if (webhookUrl(); as url) {
        <lpg-section-card heading="Webhook" class="gateway__card">
          <p class="gateway__lede">
            The webhook tells us when a customer has paid. In Razorpay, open
            <strong>Account &amp; Settings &rarr; Webhooks &rarr; Add New Webhook</strong> and
            enter:
          </p>
          <ol class="gateway__steps">
            <li>
              <strong>Webhook URL</strong> — this agency's own address:
              <code class="gateway__url">{{ url }}</code>
              <button
                pButton
                type="button"
                size="small"
                severity="secondary"
                [outlined]="true"
                (click)="copyUrl(url)"
              >
                Copy
              </button>
            </li>
            <li>
              <strong>Secret</strong> — any long random text. Type the same text into
              <em>Webhook secret</em> above and save.
            </li>
            <li>
              <strong>Active events</strong> — tick <code>payment_link.paid</code>,
              <code>payment_link.expired</code> and <code>payment_link.cancelled</code>.
            </li>
          </ol>
          @if (!settings()?.has_webhook_secret) {
            <p-message severity="warn">
              No webhook secret saved yet. Until you add one, payments are only picked up when a
              customer returns to the app, not automatically.
            </p-message>
          }
          <div class="modal-actions">
            <button
              pButton
              type="button"
              severity="secondary"
              [outlined]="true"
              [disabled]="rotating()"
              (click)="confirmRotate()"
            >
              Issue a new webhook URL
            </button>
          </div>
        </lpg-section-card>
      }
    </div>
  `,
  styles: [
    `
      .gateway {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding-block-end: var(--spacing-xl);
      }
      .gateway__card {
        inline-size: 100%;
        max-inline-size: none;
      }
      .gateway__lede {
        margin: 0 0 var(--spacing-md);
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
      .gateway__grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
        gap: var(--spacing-md);
      }
      .gateway__steps {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin: 0 0 var(--spacing-md);
        padding-inline-start: var(--spacing-lg);
        font-size: var(--typography-body-small-font-size);
      }
      .gateway__url {
        display: block;
        margin-block: var(--spacing-xs);
        word-break: break-all;
      }
    `,
  ],
})
export class OnlinePaymentSettings implements OnInit {
  private readonly service = inject(PaymentGatewayService);
  private readonly messages = inject(MessageService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly fb = inject(FormBuilder);

  protected readonly settings = signal<PaymentGatewaySettingsResponse | null>(null);
  protected readonly saving = signal(false);
  protected readonly testing = signal(false);
  protected readonly rotating = signal(false);
  protected readonly testResult = signal<{ ok: boolean; message: string } | null>(null);

  /** Full address to register in Razorpay: the site's own origin plus the agency's path. */
  protected readonly webhookUrl = computed(() => {
    const path = this.settings()?.webhook_path;
    return path ? `${window.location.origin}${path}` : '';
  });

  readonly form = this.fb.nonNullable.group({
    key_id: ['', Validators.pattern(KEY_ID_PATTERN)],
    key_secret: [''],
    webhook_secret: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  protected save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { key_id, key_secret, webhook_secret } = this.form.getRawValue();
    this.saving.set(true);
    this.service
      .save({
        key_id: key_id.trim(),
        key_secret: key_secret.trim(),
        webhook_secret: webhook_secret.trim(),
      })
      .subscribe({
        next: (saved) => {
          this.saving.set(false);
          this.testResult.set(null);
          this.apply(saved);
          this.messages.add({
            severity: 'success',
            summary: 'Saved',
            detail: 'New payment links use your Razorpay account.',
          });
        },
        // Server validation (bad key id, missing secret, test key refused) is toasted globally.
        error: () => this.saving.set(false),
      });
  }

  protected test(): void {
    this.testing.set(true);
    this.service.test().subscribe({
      next: (result) => {
        this.testing.set(false);
        this.testResult.set(result);
      },
      error: () => this.testing.set(false),
    });
  }

  protected confirmRemove(): void {
    this.confirmation.confirm({
      header: 'Remove Razorpay keys?',
      message:
        'Payment links will stop using your Razorpay account. Links already sent stay valid in Razorpay.',
      acceptLabel: 'Remove',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () =>
        this.service.remove().subscribe({
          next: () => {
            this.testResult.set(null);
            this.reload();
            this.messages.add({ severity: 'success', summary: 'Keys removed' });
          },
        }),
    });
  }

  protected confirmRotate(): void {
    this.confirmation.confirm({
      header: 'Issue a new webhook URL?',
      message:
        'The current URL stops working at once. Update the webhook in Razorpay with the new address, or payments will not be picked up automatically.',
      acceptLabel: 'Issue new URL',
      rejectLabel: 'Cancel',
      accept: () => {
        this.rotating.set(true);
        this.service.rotateWebhookUrl().subscribe({
          next: (rotated) => {
            this.rotating.set(false);
            this.apply(rotated);
          },
          error: () => this.rotating.set(false),
        });
      },
    });
  }

  protected copyUrl(url: string): void {
    void navigator.clipboard
      ?.writeText(url)
      .then(() => this.messages.add({ severity: 'success', summary: 'Copied' }));
  }

  private reload(): void {
    this.service
      .get()
      .subscribe({ next: (current) => this.apply(current), error: () => undefined });
  }

  private apply(current: PaymentGatewaySettingsResponse): void {
    this.settings.set(current);
    this.form.reset({ key_id: '', key_secret: '', webhook_secret: '' });
    // Nothing saved yet: both halves of the key are needed.
    const { key_id, key_secret } = this.form.controls;
    key_id.setValidators(
      current.configured
        ? [Validators.pattern(KEY_ID_PATTERN)]
        : [Validators.required, Validators.pattern(KEY_ID_PATTERN)],
    );
    key_secret.setValidators(current.has_key_secret ? [] : [Validators.required]);
    key_id.updateValueAndValidity();
    key_secret.updateValueAndValidity();
  }
}
