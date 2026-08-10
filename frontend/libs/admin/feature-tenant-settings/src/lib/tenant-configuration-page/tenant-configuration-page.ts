import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AdminTenantConfigurationService,
  type AppError,
  type TenantConfigurationResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

const RECOGNIZED_CONFIG_KEYS = [
  'gst_rate_percent',
  'cancellation_fee_amount',
  'credit_limit_default',
] as const;

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the configuration value. Please try again.';
  }
}

/**
 * Tenant configuration history + set-new-value form — `tenant:configure`.
 *
 * Historized (BR-31): "setting" a value always adds a new row with a later
 * `effective_from`, it never edits an existing one — the grid below shows
 * the full history, not just the current value.
 */
@Component({
  selector: 'lpg-tenant-configuration-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Tenant Configuration</h1>
      <p>Values are historized — setting a new value never overwrites the previous one.</p>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="entries()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Tenant configuration history"
        />
      </div>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Set a configuration value</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="config-key">Key</label>
          <select id="config-key" formControlName="configKey">
            <option value="" disabled>Select a key</option>
            @for (key of recognizedKeys; track key) {
              <option [value]="key">{{ key }}</option>
            }
          </select>
        </div>
        <div class="admin-page__field">
          <label for="config-value">Value</label>
          <input pInputText id="config-value" type="text" formControlName="configValue" />
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Set value' }}
        </button>
      </form>
    </div>
  `,
  styles: [
    `
      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
      }

      .admin-page__grid {
        block-size: 400px;
      }

      .admin-page__form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        max-inline-size: 24rem;
      }

      .admin-page__field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }
    `,
  ],
})
export class TenantConfigurationPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly configService = inject(AdminTenantConfigurationService);

  protected readonly entries = signal<TenantConfigurationResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly recognizedKeys = RECOGNIZED_CONFIG_KEYS;

  protected readonly columns: DataGridColumn<TenantConfigurationResponse>[] = [
    { field: 'config_key', header: 'Key', sortable: true, filterable: true },
    {
      field: 'config_value',
      header: 'Value',
      valueFormatter: (value) => JSON.stringify(value),
    },
    { field: 'effective_from', header: 'Effective From', sortable: true },
  ];

  protected readonly form = this.formBuilder.group({
    configKey: ['', [Validators.required]],
    configValue: ['', [Validators.required]],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.configService.listConfiguration().subscribe({
      next: (entries) => {
        this.entries.set(entries);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    const { configKey, configValue } = this.form.getRawValue();

    this.configService.setConfiguration(configKey, configValue).subscribe({
      next: () => {
        this.submitting.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
