import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
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
 * Tenant configuration history + set-new-value drawer — `tenant:configure`.
 *
 * Historized (BR-31): "setting" a value always adds a new row with a later
 * `effective_from`, it never edits an existing one — the grid below shows
 * the full history, not just the current value.
 */
@Component({
  selector: 'lpg-tenant-configuration-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, Select, Drawer, IconField, InputIcon],
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
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Set Value</span></button>
          </div>
</ng-template>
      </div>
      <p class="page-note">Values are historized — setting a new value never overwrites the previous one.</p>

      @if (entries().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon styleClass="pi pi-search" />
              <input pInputText type="text" placeholder="Search configuration..." class="w-full" />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
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
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="entries()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Tenant configuration history"
            />
          </div>
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
          <p class="page-lede">This creates a new historized entry — the previous value is preserved.</p>

          <div class="form-group">
            <label for="config-key">Key</label>
            <p-select
              id="config-key"
              formControlName="configKey"
              [options]="recognizedKeys"
              placeholder="Select a key"
              styleClass="w-full"
              appendTo="body">
            </p-select>
            @if (form.controls.configKey.touched && form.controls.configKey.invalid) {
              <small class="field-error">Configuration key is required.</small>
            }
          </div>

          <div class="form-group">
            <label for="config-value">Value</label>
            <input pInputText id="config-value" type="text" formControlName="configValue" placeholder="e.g. 18" />
            @if (form.controls.configValue.touched && form.controls.configValue.invalid) {
              <small class="field-error">Value is required.</small>
            }
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

      .grid-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-block-size: 0;
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
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
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly recognizedKeys = [...RECOGNIZED_CONFIG_KEYS];

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
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `"${configKey}" saved.` });
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
