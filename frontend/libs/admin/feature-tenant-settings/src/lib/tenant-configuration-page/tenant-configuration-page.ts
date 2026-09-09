import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { TooltipModule } from 'primeng/tooltip';
import { MessageService } from 'primeng/api';
import {
  AdminTenantConfigurationService,
  type AppError,
  type TenantConfigurationResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent, formatTimestamp } from '@lpg/shared/ui';

/** The recognized config-key catalog, each with a human-readable label and
 * a description of what it controls — mirrors the backend's
 * `RECOGNIZED_CONFIG_KEYS` (`domain/tenant/tenant_configuration.py`). Order
 * here is display order in the "Set a configuration value" dropdown. */
const CONFIG_KEY_INFO: Record<string, { label: string; description: string }> = {
  gst_rate_percent: {
    label: 'GST Rate (%)',
    description:
      'The GST tax rate applied when computing invoice tax at issuance (BR-16). Historized so a past invoice stays reproducible against the rate that was actually in effect when it was issued.',
  },
  cancellation_fee_amount: {
    label: 'Cancellation Fee Amount',
    description:
      "Flat fee charged to a customer when an order is cancelled, per the tenant's cancellation policy.",
  },
  credit_limit_default: {
    label: 'Default Credit Limit',
    description:
      "Default outstanding-balance credit limit applied to a customer's account when no more specific override exists.",
  },
  ai_gateway_enabled: {
    label: 'AI Gateway Enabled',
    description:
      'Tenant opt-in for the AI Command Center (ADR-045) — defaults to off (any falsy or absent value). Set to true to enable; set to false to disable. Live-verified: a value of the literal text "false" is correctly read as disabled, not truthy.',
  },
  ai_daily_token_budget: {
    label: 'AI Daily Token Budget',
    description:
      "Optional override of the AI Command Center's daily token ceiling — falls back to a platform default (100,000) when unset. A whole number, e.g. 50000.",
  },
};

const RECOGNIZED_CONFIG_KEYS = [
  'gst_rate_percent',
  'cancellation_fee_amount',
  'credit_limit_default',
  'ai_gateway_enabled',
  'ai_daily_token_budget',
] as const;

/** Best-effort label for a config key the frontend's catalog doesn't
 * recognize yet — the backend allows new keys without a schema change
 * (`config_value` is jsonb), so the frontend catalog can legitimately lag
 * behind. Falls back to a naive Title Case of the raw key rather than
 * showing nothing. */
function humanizeConfigKey(key: string): string {
  return CONFIG_KEY_INFO[key]?.label ?? key.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the configuration value. Please try again.';
  }
}

/** AG Grid cell renderer for the config-key column: an info icon (hover for
 * the key's description) followed by its human-readable label — the raw
 * `gst_rate_percent`-style key is never the only thing shown. */
@Component({
  selector: 'lpg-config-key-cell',
  standalone: true,
  imports: [TooltipModule],
  template: `
    <div style="display: flex; align-items: center; gap: 0.5rem; height: 100%;">
      @if (description()) {
        <i
          class="pi pi-info-circle"
          style="opacity: 0.6; font-size: 0.875rem; cursor: help;"
          [pTooltip]="description()"
          tooltipPosition="top"
        ></i>
      }
      <span>{{ label() }}</span>
    </div>
  `,
})
class ConfigKeyCell {
  protected readonly label = signal('');
  protected readonly description = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const key = String(params.value ?? '');
    this.label.set(humanizeConfigKey(key));
    this.description.set(CONFIG_KEY_INFO[key]?.description ?? '');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/**
 * Tenant configuration history + set-new-value drawer — `tenant:configure`.
 *
 * Historized (BR-31): "setting" a value always adds a new row with a later
 * `effective_from`, it never edits an existing one — the grid below shows
 * the full history, not just the current value.
 */
@Component({
  selector: 'lpg-tenant-configuration-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, RouterLink, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, FormFieldComponent, Select, Drawer, DrawerA11yDirective, IconField, InputIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Tenant Configuration</h1>
          <p class="page-subtitle">Manage tenant-wide settings like GST rates and credit limits.</p>
        </div>
    </ng-template>
      </div>
      <p class="page-note">Values are historized — setting a new value never overwrites the previous one.</p>

      <div class="structured-editors">
        <span class="structured-editors__label">Structured editors:</span>
        <a routerLink="/admin/tenant-config/tdt-rating" class="structured-editors__link">
          <i class="pi pi-star-fill" aria-hidden="true"></i>
          TDT Rating (bands &amp; fine schedule)
        </a>
      </div>

      @if (entries().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search configuration..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Set Value</span></button>
          </div>
        </div>
      }

      @if (!loading() && entries().length === 0) {
        <div class="empty-state">
          <i class="pi pi-sliders-h empty-state__icon"></i>
          <p class="empty-state__title">No configuration values</p>
          <p class="empty-state__description">Set the first configuration value to get started.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Set Value</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="entries()"
            [columns]="columns"
            [loading]="loading()"
            [searchQuery]="searchQuery()"
            ariaLabel="Tenant configuration history"
          />
        </section>
      }

      <!-- Set Configuration Value Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Set a configuration value"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="setConfigForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
          <p class="page-lede">This creates a new historized entry — the previous value is preserved.</p>

          <lpg-form-field label="Key" for="config-key" [control]="form.controls.configKey" [messages]="{ required: 'Configuration key is required.' }">
            <p-select
              inputId="config-key"
              formControlName="configKey"
              [options]="recognizedKeys"
              optionLabel="label"
              optionValue="value"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>

          <lpg-form-field label="Value" for="config-value" [control]="form.controls.configValue" [messages]="{ required: 'Value is required.' }">
            <input pInputText id="config-value" type="text" formControlName="configValue" placeholder="e.g. 18" [fluid]="true" />
          </lpg-form-field>
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Save value
            </button>
          </div>
        </form>
      </p-drawer>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .admin-page {
        display: flex;
        flex-direction: column;
        block-size: 100%;
      }

      .page-note {
        margin: 0 0 var(--spacing-sm) 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      /* Structured editors — a small number of config keys (arrays of
         bands/rules, not a single scalar) get a dedicated sub-form instead
         of the generic "Set Value" drawer's single-line input; linked from
         here rather than added as a new top-level nav entry. */
      .structured-editors {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        margin-block-end: var(--spacing-md);
      }

      .structured-editors__label {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .structured-editors__link {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        padding: var(--spacing-xs) var(--spacing-sm);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-full);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-primary);
        text-decoration: none;
        transition: border-color var(--motion-duration-small) var(--motion-easing-emphasized);
      }

      .structured-editors__link:hover {
        border-color: var(--color-action-primary);
        color: var(--color-action-primary);
      }

      .structured-editors__link i {
        color: var(--color-status-warning);
      }

    `,
  ],
})
export class TenantConfigurationPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly configService = inject(AdminTenantConfigurationService);
  private readonly messageService = inject(MessageService);

  protected readonly entries = signal<TenantConfigurationResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly recognizedKeys = RECOGNIZED_CONFIG_KEYS.map((key) => ({
    label: CONFIG_KEY_INFO[key].label,
    value: key,
  }));

  protected readonly columns: DataGridColumn<TenantConfigurationResponse>[] = [
    { field: 'config_key', header: 'Key', sortable: true, filterable: true, cellRenderer: ConfigKeyCell },
    {
      field: 'config_value',
      header: 'Value',
      valueFormatter: (value) => JSON.stringify(value),
    },
    {
      field: 'effective_from',
      header: 'Effective From',
      sortable: true,
      valueFormatter: (value) => formatTimestamp(value),
    },
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

  protected openCreateDrawer(): void {
    this.form.reset();
    this.createDrawerVisible.set(true);
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
    const { configKey, configValue } = this.form.getRawValue();

    this.configService.setConfiguration(configKey, configValue).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `"${humanizeConfigKey(configKey)}" saved.` });
        this.createDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
