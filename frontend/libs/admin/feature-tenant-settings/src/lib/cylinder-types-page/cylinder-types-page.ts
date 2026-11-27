import { ConfirmationService } from 'primeng/api';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  viewChild,
  computed,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { Select } from 'primeng/select';
import { selectableByName } from '@lpg/shared/util';
import {
  AdminBranchService,
  AdminCylinderTypeService,
  AdminPriceListService,
  AdminTenantConfigurationService,
  NotifyService,
  type BranchResponse,
  type CylinderSizeResponse,
  type CylinderTypeResponse,
  type PriceListEntryResponse,
  errorMessageFor,
} from '@lpg/shared/data-access';
import {
  DrawerA11yDirective,
  ExportButtonComponent,
  FormFieldComponent,
  HeaderTitlePortalDirective,
  PageActionsDirective,
  PageHeaderComponent,
  StatusChipCell,
  formatCurrencyInr,
} from '@lpg/shared/ui';
import { DataGridComponent, rowActionsColumn, type DataGridColumn } from '@lpg/shared/ui/data-grid';
import { CylinderTypeDrawer } from './cylinder-type-drawer';
import {
  GST_RATE_HINT,
  GST_RATE_MESSAGES,
  HSN_MESSAGES,
  HSN_PATTERN,
  LPG_HSN_CODE,
  categoryOptions,
  sizesIn,
  sizesNotTaken,
} from './cylinder-type-fields';
import {
  defaultCustomerType,
  gstRateWarning,
  includesGstFrom,
  priceHeadline,
  priceHeadlineText,
  priceHint,
  usualGstRate,
} from './price-book';
import { PriceDrawer } from './price-drawer';
import { RateProposalsCard } from './rate-proposals-card';

/** A cylinder with the price the list shows for it. */
type CylinderRow = CylinderTypeResponse & {
  readonly price_text: string;
  readonly has_price: boolean;
};

/**
 * The cylinders an agency sells: picked from the standard size list, each with
 * its price and GST on the one screen — `tenant:configure`.
 */
@Component({
  selector: 'lpg-cylinder-types-page',
  standalone: true,
  imports: [
    ExportButtonComponent,
    PageActionsDirective,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
    Select,
    CylinderTypeDrawer,
    PriceDrawer,
    RateProposalsCard,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header
            title="Cylinders & Prices"
            subtitle="The cylinders you sell, what they cost and their GST."
          />
        </ng-template>
      </div>

      @if (unclassifiedCount() > 0) {
        <div class="gst-warning" role="status">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>
            {{ unclassifiedCount() }} cylinder
            {{ unclassifiedCount() === 1 ? 'type has' : 'types have' }} no GST rate. Deliveries of
            them are held, not invoiced, until you set one with “Set GST”.
          </span>
        </div>
      }

      @if (rateWarnings().length > 0) {
        <div class="gst-warning" role="status">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>
            @for (item of rateWarnings(); track item.id) {
              <span class="gst-warning__item">
                <strong>{{ item.name }}</strong
                >: {{ item.warning }}
              </span>
            }
          </span>
        </div>
      }

      <lpg-rate-proposals-card [cylinderTypes]="cylinderTypes()" (accepted)="reload()" />

      @if (offList().length > 0) {
        <div class="gst-warning" role="status">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>
            Not a standard cylinder size: {{ offList().join(', ') }}. Select the name to fix it.
          </span>
        </div>
      }

      @if (cylinderTypes().length > 0) {
        <ng-template lpgPageActions>
          <button pButton (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add cylinder</span>
          </button>
        </ng-template>
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield>
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search cylinders..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
            <span class="data-toolbar__spacer"></span>
            <lpg-export-button (export)="exportCsv()" />
          </div>
        </div>
      }

      @if (!loading() && !loadError() && cylinderTypes().length === 0) {
        <div class="empty-state">
          <i class="pi pi-box empty-state__icon"></i>
          <p class="empty-state__title">No cylinders yet</p>
          <p class="empty-state__description">Add the first cylinder you sell, with its price.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add cylinder</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="rows()"
            [columns]="columns"
            [loading]="loading()"
            [error]="loadError()"
            (retry)="reload()"
            [searchQuery]="searchQuery()"
            ariaLabel="Cylinders and prices"
          />
        </section>
      }

      <!-- Add a cylinder, with its price -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Add a cylinder"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: 'var(--drawer-width)' }"
      >
        <form
          id="addCylinderTypeForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <p class="page-lede">Pick the cylinder and set its price.</p>

            @if (sizesError(); as error) {
              <div class="inline-note" role="alert">
                <span>Couldn't load the cylinder sizes. {{ error }}</span>
                <button
                  pButton
                  type="button"
                  size="small"
                  severity="secondary"
                  (click)="loadSizes()"
                >
                  Retry
                </button>
              </div>
            } @else if (sizes().length > 0 && availableSizes().length === 0) {
              <p class="inline-note" role="status">
                Every standard size is already in your cylinder types.
              </p>
            }

            <lpg-form-field
              label="Cylinder type"
              for="cylinder-category"
              [control]="form.controls.category"
              [messages]="{ required: 'Choose a cylinder type.' }"
            >
              <p-select
                [filter]="true"
                [resetFilterOnHide]="true"
                inputId="cylinder-category"
                formControlName="category"
                [options]="availableCategories()"
                optionLabel="label"
                optionValue="value"
                placeholder="Choose a type"
                [emptyMessage]="noOptionsMessage()"
                appendTo="body"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Cylinder size"
              for="cylinder-size"
              [control]="form.controls.sizeCode"
              [messages]="{ required: 'Choose a cylinder size.' }"
            >
              <p-select
                [filter]="true"
                [resetFilterOnHide]="true"
                inputId="cylinder-size"
                formControlName="sizeCode"
                [options]="sizesOfChosenType()"
                optionLabel="name"
                optionValue="code"
                placeholder="Choose a size"
                [emptyMessage]="noOptionsMessage()"
                appendTo="body"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Price (₹)"
              for="cylinder-price"
              [control]="form.controls.price"
              [hint]="newPriceHint()"
              [messages]="{ required: 'Enter the price.', min: 'The price must be above 0.' }"
            >
              <input
                pInputText
                id="cylinder-price"
                type="number"
                step="0.01"
                inputmode="decimal"
                formControlName="price"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="GST rate (%)"
              for="cylinder-gst"
              [control]="form.controls.gstRatePercent"
              [hint]="newGstHint()"
              [messages]="gstMessages"
            >
              <input
                pInputText
                id="cylinder-gst"
                type="number"
                step="0.01"
                formControlName="gstRatePercent"
                [fluid]="true"
              />
            </lpg-form-field>

            <details class="more-options">
              <summary>More options</summary>
              <lpg-form-field
                label="HSN code"
                for="cylinder-hsn"
                [control]="form.controls.hsnCode"
                hint="The GST code for LPG. Change it only if your accountant says so."
                [messages]="hsnMessages"
              >
                <input
                  pInputText
                  id="cylinder-hsn"
                  inputmode="numeric"
                  formControlName="hsnCode"
                  [fluid]="true"
                />
              </lpg-form-field>
            </details>
          </div>

          <div class="modal-actions">
            <button
              pButton
              type="button"
              severity="secondary"
              (click)="createDrawerVisible.set(false)"
            >
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting()">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save cylinder
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Set GST (DA-06) -->
      <p-drawer
        [visible]="!!gstTarget()"
        (onHide)="gstTarget.set(null)"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Set GST"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: 'var(--drawer-width)' }"
      >
        <form [formGroup]="gstForm" (ngSubmit)="saveGst()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
            <p class="page-lede">
              Invoices for <strong>{{ gstTarget()?.name }}</strong> use this HSN code and rate from
              now on. Invoices already issued are not changed.
            </p>
            <lpg-form-field
              label="HSN code"
              for="gst-hsn"
              [control]="gstForm.controls.hsnCode"
              [messages]="hsnMessages"
            >
              <input
                pInputText
                id="gst-hsn"
                inputmode="numeric"
                formControlName="hsnCode"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="GST rate (%)"
              for="gst-rate"
              [control]="gstForm.controls.gstRatePercent"
              [hint]="gstHint"
              [messages]="gstMessages"
            >
              <input
                pInputText
                id="gst-rate"
                type="number"
                step="0.01"
                formControlName="gstRatePercent"
                [fluid]="true"
              />
            </lpg-form-field>
          </div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="gstTarget.set(null)">
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting() || gstForm.invalid">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save GST
            </button>
          </div>
        </form>
      </p-drawer>

      <lpg-cylinder-type-drawer
        [cylinderType]="details()"
        [allTypes]="cylinderTypes()"
        [sizes]="sizes()"
        [prices]="prices()"
        [branches]="branches()"
        (priceRequested)="openPriceDrawer($event)"
        (closed)="detailsId.set(null)"
        (saved)="reload()"
        (deleted)="onDeleted()"
        (activeToggled)="toggleActive($event)"
      />

      <lpg-price-drawer
        [cylinderType]="priceTarget()"
        [suggestedPrice]="suggestedPrice()"
        [prices]="prices()"
        [branches]="selectableBranches()"
        [includesGst]="pricesIncludeGst()"
        (closed)="priceTarget.set(null)"
        (saved)="onPriceSaved()"
      />
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

      .gst-warning {
        display: flex;
        gap: var(--spacing-sm);
        align-items: flex-start;
        margin-block-end: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border: var(--border-width) solid var(--color-status-warning);
        border-radius: var(--radius-md);
      }

      .gst-warning__item {
        display: block;
      }

      .gst-warning > .pi {
        color: var(--color-status-warning);
      }

      :host ::ng-deep .cell--warning {
        color: var(--color-status-warning);
      }

      .inline-note {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      .more-options summary {
        cursor: pointer;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      .more-options[open] summary {
        margin-block-end: var(--spacing-sm);
      }
    `,
  ],
})
export class CylinderTypesPage implements OnInit {
  private readonly grid = viewChild(DataGridComponent);

  /** DA-14: the grid as shown (filtered, sorted, formatted) as a CSV file. */
  protected exportCsv(): void {
    this.grid()?.exportCsv('cylinders-and-prices');
  }

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly priceListService = inject(AdminPriceListService);
  private readonly branchService = inject(AdminBranchService);
  private readonly configurationService = inject(AdminTenantConfigurationService);
  private readonly notify = inject(NotifyService);
  private readonly confirmation = inject(ConfirmationService);

  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly prices = signal<PriceListEntryResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  /** Only active, named branches can be given a price of their own (DA-19). */
  protected readonly selectableBranches = computed(() => selectableByName(this.branches()));
  protected readonly pricesIncludeGst = signal(false);
  protected readonly rows = computed<CylinderRow[]>(() =>
    this.cylinderTypes().map((type) => {
      const headline = priceHeadline(this.prices(), type.id, type.category);
      return {
        ...type,
        price_text: priceHeadlineText(headline),
        has_price: !!headline.entry,
      };
    }),
  );
  protected readonly priceTarget = signal<CylinderTypeResponse | null>(null);
  protected readonly suggestedPrice = signal<number | null>(null);
  protected readonly loading = signal(false);
  /** Set when the list failed to load — the grid shows it with Retry (QA DA-15). */
  protected readonly loadError = signal<string | null>(null);
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly gstTarget = signal<CylinderTypeResponse | null>(null);
  protected readonly unclassifiedCount = computed(
    () => this.cylinderTypes().filter((c) => c.is_active && c.gst_rate_percent == null).length,
  );

  /** Cylinders on sale whose saved rate is not the usual one for their type. */
  protected readonly rateWarnings = computed(() =>
    this.cylinderTypes().flatMap((c) => {
      const warning = c.is_active ? gstRateWarning(c.category, c.gst_rate_percent) : null;
      return warning ? [{ id: c.id, name: c.name, warning }] : [];
    }),
  );

  protected readonly sizes = signal<CylinderSizeResponse[]>([]);
  protected readonly sizesError = signal<string | null>(null);
  /** Standard sizes the agency has not added yet. */
  protected readonly availableSizes = computed(() =>
    sizesNotTaken(this.sizes(), this.cylinderTypes()),
  );
  protected readonly availableCategories = computed(() => categoryOptions(this.availableSizes()));
  /** Active records typed before the standard list existed. */
  protected readonly offList = computed(() =>
    this.cylinderTypes()
      .filter((c) => c.is_active && !c.size_code)
      .map((c) => c.name),
  );

  protected readonly detailsId = signal<string | null>(null);
  /** Looked up in the list, so the drawer follows a reload. */
  protected readonly details = computed(
    () => this.cylinderTypes().find((c) => c.id === this.detailsId()) ?? null,
  );

  protected readonly gstHint = GST_RATE_HINT;
  protected readonly hsnMessages = HSN_MESSAGES;
  protected readonly gstMessages = GST_RATE_MESSAGES;

  protected readonly columns: DataGridColumn<CylinderRow>[] = [
    {
      field: 'name',
      header: 'Name',
      sortable: true,
      filterable: true,
      // Wide enough for the longest standard size name.
      minWidth: 200,
      onLinkClick: (row) => this.detailsId.set(row.id),
    },
    {
      field: 'weight_kg',
      header: 'Weight (kg)',
      sortable: true,
      numeric: true,
      priority: 'low',
    },
    {
      field: 'price_text',
      header: 'Price',
      sortable: true,
      numeric: true,
      minWidth: 150,
      cellClass: (value) => (value === 'Not set' ? 'cell--warning' : ''),
    },
    {
      field: 'gst_rate_percent',
      header: 'GST',
      sortable: true,
      numeric: true,
      valueFormatter: (value) => (value == null ? 'Not set' : `${Number(value)}%`),
      cellClass: (value) => (value == null ? 'cell--warning' : ''),
    },
    {
      field: 'is_active',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        labelMap: { true: 'Active', false: 'Inactive' },
        severityMap: { true: 'success', false: 'secondary' },
      },
      // What the quick search matches and a CSV download holds.
      valueFormatter: (value) => (value ? 'Active' : 'Inactive'),
    },
    rowActionsColumn<CylinderRow>([
      {
        icon: 'pi pi-indian-rupee',
        text: (row) => (row.has_price ? 'Change price' : 'Set price'),
        label: (row) => `${row.has_price ? 'Change' : 'Set'} price of ${row.name}`,
        visible: (row) => row.is_active,
        onAction: (row) => this.openPriceDrawer(row),
      },
      // A first-time shortcut; later changes are made in the drawer.
      {
        icon: 'pi pi-percentage',
        text: 'Set GST',
        label: (row) => `Set GST for ${row.name}`,
        visible: (row) => row.gst_rate_percent == null,
        onAction: (row) => this.openGstDrawer(row),
      },
      {
        icon: (row) => (row.is_active ? 'pi pi-ban' : 'pi pi-check-circle'),
        text: (row) => (row.is_active ? 'Deactivate' : 'Activate'),
        severity: (row) => (row.is_active ? 'danger' : 'primary'),
        label: (row) => `${row.is_active ? 'Deactivate' : 'Activate'} ${row.name}`,
        onAction: (row) => this.toggleActive(row),
      },
    ]),
  ];

  protected readonly form = this.formBuilder.group({
    category: [null as string | null, [Validators.required]],
    sizeCode: [null as string | null, [Validators.required]],
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
    price: [null as number | null, [Validators.required, Validators.min(0.01)]],
  });

  private readonly formValues = toSignal(this.form.valueChanges, { initialValue: this.form.value });
  protected readonly newPriceHint = computed(() => {
    const { gstRatePercent, price, category } = this.formValues();
    const customer = defaultCustomerType(category);
    return `For ${customer} customers. ${priceHint(this.pricesIncludeGst(), gstRatePercent, price)}`;
  });

  protected readonly newGstHint = computed(() => {
    const { gstRatePercent, category } = this.formValues();
    return gstRateWarning(category, gstRatePercent) ?? GST_RATE_HINT;
  });

  private readonly chosenCategory = toSignal(this.form.controls.category.valueChanges, {
    initialValue: null,
  });
  protected readonly sizesOfChosenType = computed(() =>
    sizesIn(this.availableSizes(), this.chosenCategory()),
  );
  /** What an empty dropdown says, in place of "No results found". */
  protected readonly noOptionsMessage = computed(() => {
    if (this.sizesError()) return "The sizes didn't load. Use Retry above.";
    return this.chosenCategory() ? 'No sizes left to add.' : 'Choose a cylinder type first.';
  });

  constructor() {
    // A size belongs to one type, so changing the type clears the size. The
    // type also decides the usual GST rate, unless the admin typed their own.
    this.form.controls.category.valueChanges.pipe(takeUntilDestroyed()).subscribe((category) => {
      this.form.controls.sizeCode.reset(null);
      const rate = this.form.controls.gstRatePercent;
      if (rate.pristine) rate.setValue(usualGstRate(category));
    });
  }

  protected readonly gstForm = this.formBuilder.group({
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
  });

  ngOnInit(): void {
    this.reload();
    this.loadSizes();
    this.branchService.listBranches().subscribe({
      next: (branches) => this.branches.set(branches),
      // Without branches, prices are still set for all of them.
      error: () => this.branches.set([]),
    });
    this.configurationService.getEffectiveConfiguration('prices_include_gst').subscribe({
      next: (config) => this.pricesIncludeGst.set(includesGstFrom(config?.config_value)),
      error: () => this.pricesIncludeGst.set(false),
    });
  }

  protected loadSizes(): void {
    this.sizesError.set(null);
    this.cylinderTypeService.listCylinderSizes().subscribe({
      next: (sizes) => this.sizes.set(sizes),
      error: (error: unknown) => this.sizesError.set(errorMessageFor(error)),
    });
  }

  protected onDeleted(): void {
    this.detailsId.set(null);
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.loadError.set(null);
    forkJoin({
      cylinderTypes: this.cylinderTypeService.listCylinderTypes(),
      prices: this.priceListService.listPrices(),
    }).subscribe({
      next: ({ cylinderTypes, prices }) => {
        this.cylinderTypes.set(cylinderTypes);
        this.prices.set(prices);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(errorMessageFor(error));
        this.loading.set(false);
      },
    });
  }

  protected openCreateDrawer(): void {
    this.resetCreateForm();
    this.createDrawerVisible.set(true);
  }

  private resetCreateForm(): void {
    this.form.reset({
      category: null,
      sizeCode: null,
      hsnCode: LPG_HSN_CODE,
      gstRatePercent: null,
      price: null,
    });
  }

  protected openPriceDrawer(cylinderType: CylinderTypeResponse, suggested: number | null = null) {
    this.suggestedPrice.set(suggested);
    this.priceTarget.set(cylinderType);
  }

  protected onPriceSaved(): void {
    this.priceTarget.set(null);
    this.reload();
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    const { category, sizeCode, hsnCode, gstRatePercent, price } = this.form.getRawValue();
    if (this.form.invalid || !sizeCode) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.cylinderTypeService
      .createCylinderType(sizeCode, { hsnCode, gstRatePercent: Number(gstRatePercent) })
      .subscribe({
        next: (created) =>
          this.savePrice(created, defaultCustomerType(created.category ?? category), Number(price)),
        error: () => this.submitting.set(false),
      });
  }

  /** The cylinder exists by now. If its price cannot be saved, the price
   * drawer opens with it filled in, so nothing has to be added twice. */
  private savePrice(created: CylinderTypeResponse, customerType: string, price: number): void {
    const close = (): void => {
      this.submitting.set(false);
      this.createDrawerVisible.set(false);
      this.resetCreateForm();
      this.reload();
    };
    this.priceListService.setPrice(created.id, customerType, price).subscribe({
      next: () => {
        close();
        this.notify.success(`"${created.name}" added at ${formatCurrencyInr(price)}.`);
      },
      error: () => {
        close();
        this.openPriceDrawer(created, price);
      },
    });
  }

  protected openGstDrawer(cylinderType: CylinderTypeResponse): void {
    this.gstForm.reset({
      hsnCode: cylinderType.hsn_code ?? LPG_HSN_CODE,
      gstRatePercent:
        cylinderType.gst_rate_percent == null ? null : Number(cylinderType.gst_rate_percent),
    });
    this.gstTarget.set(cylinderType);
  }

  protected saveGst(): void {
    const target = this.gstTarget();
    if (!target || this.gstForm.invalid || this.submitting()) {
      this.gstForm.markAllAsTouched();
      return;
    }
    const { hsnCode, gstRatePercent } = this.gstForm.getRawValue();
    this.submitting.set(true);
    this.cylinderTypeService.classifyForGst(target.id, hsnCode, Number(gstRatePercent)).subscribe({
      next: () => {
        this.submitting.set(false);
        this.gstTarget.set(null);
        this.notify.success(`GST for "${target.name}" saved.`);
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }

  protected toggleActive(cylinderType: CylinderTypeResponse): void {
    if (!cylinderType.is_active) {
      this.setActive(cylinderType, true);
      return;
    }
    this.confirmation.confirm({
      header: 'Deactivate cylinder type?',
      message: `"${cylinderType.name}" will no longer be offered in forms. You can activate it again later.`,
      acceptLabel: 'Deactivate',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.setActive(cylinderType, false),
    });
  }

  private setActive(cylinderType: CylinderTypeResponse, nextActive: boolean): void {
    this.cylinderTypeService.setActive(cylinderType.id, nextActive).subscribe({
      next: () => {
        this.notify.success(`"${cylinderType.name}" ${nextActive ? 'activated' : 'deactivated'}.`);
        this.reload();
      },
    });
  }
}
