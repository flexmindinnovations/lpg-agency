import {
  ChangeDetectionStrategy,
  Component,
  effect,
  PLATFORM_ID,
  inject,
  signal,
  OnDestroy,
  ElementRef,
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { ChartModule } from 'primeng/chart';
import { catchError, of } from 'rxjs';
import {
  ActionChipCell,
  CopyableIdCell,
  DataGridComponent,
  DataGridColumn,
  formatEntityName,
  formatTimestamp,
} from '@lpg/shared/ui';
import {
  DashboardService,
  type CylinderTypePriceCardResponse,
  type DashboardActivityEntryResponse,
  type DashboardSummaryResponse,
} from '@lpg/shared/data-access';

interface KpiData {
  title: string;
  value: string;
  icon: string;
  colorClass: string;
}

interface InventoryStatusCard {
  status: string;
  label: string;
  quantity: number;
}

const STATUS_LABELS: Record<string, string> = {
  filled: 'Filled',
  empty: 'Empty',
  damaged: 'Damaged',
  leakage: 'Leakage',
  quarantine: 'Quarantine',
  repair: 'Repair',
  scrap: 'Scrap',
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function escapeCsvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

@Component({
  selector: 'lpg-home',
  standalone: true,
  imports: [ButtonDirective, ButtonIcon, ButtonLabel, ChartModule, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dashboard">
      <div class="page-header">
        <div class="page-header__text">
          <h1 class="page-title">Agency Overview</h1>
          <p class="page-subtitle">
            Live summary of your agency's operational data across every module.
          </p>
        </div>
        <div class="page-header__actions">
          <button
            pButton
            severity="secondary"
            [disabled]="loading()"
            (click)="exportReport()"
          >
            <i pButtonIcon class="pi pi-download"></i>
            <span pButtonLabel>Export Report</span>
          </button>
          <button pButton type="button" (click)="onNewBooking()">
            <i pButtonIcon class="pi pi-plus"></i>
            <span pButtonLabel>New Booking</span>
          </button>
        </div>
      </div>

      <!-- KPI Section -->
      <section class="dashboard__kpis">
        @for (kpi of kpis(); track kpi.title) {
          <div class="kpi-card">
            <div class="kpi-card__header">
              <span class="kpi-card__title">{{ kpi.title }}</span>
              <div class="kpi-card__icon" [class]="kpi.colorClass">
                <i [class]="kpi.icon" aria-hidden="true"></i>
              </div>
            </div>
            <div class="kpi-card__value">{{ loading() ? '—' : kpi.value }}</div>
          </div>
        }
      </section>

      <!-- Charts Section -->
      <section class="dashboard__charts">
        <div class="panel">
          <div class="panel-header">
            <h2 class="section-heading">Fleet Status</h2>
          </div>
          <div class="panel-content chart-container">
            @if (isBrowser) {
              <p-chart type="bar" [data]="vehicleStatusChartData()" [options]="barChartOptions()"></p-chart>
            }
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <h2 class="section-heading">Cylinder Inventory (All Locations)</h2>
          </div>
          <div class="panel-content chart-container">
            @if (isBrowser) {
              <p-chart type="doughnut" [data]="inventoryChartData()" [options]="doughnutChartOptions()"></p-chart>
            }
          </div>
        </div>
      </section>

      <!-- Inventory Detail Cards -->
      <section class="dashboard__section">
        <h2 class="section-heading">Inventory by Status</h2>
        @if (inventoryCards().length > 0) {
          <div class="inventory-cards">
            @for (card of inventoryCards(); track card.status) {
              <div class="inventory-card">
                <span class="inventory-card__label">{{ card.label }}</span>
                <span class="inventory-card__value">{{ card.quantity.toLocaleString() }}</span>
              </div>
            }
          </div>
        } @else if (!loading()) {
          <p class="empty-state">No inventory activity recorded yet.</p>
        }
      </section>

      <!-- Price Cards -->
      <section class="dashboard__section">
        <h2 class="section-heading">Cylinder Pricing (Domestic)</h2>
        @if (priceCards().length > 0) {
          <div class="price-cards">
            @for (card of priceCards(); track card.cylinder_type_id) {
              <div class="price-card">
                <span class="price-card__name">{{ card.name }}</span>
                <span class="price-card__weight">{{ card.weight_kg }} kg</span>
                <span class="price-card__price">
                  {{ card.price ? '₹' + card.price : 'Not configured' }}
                </span>
              </div>
            }
          </div>
        } @else if (!loading()) {
          <p class="empty-state">No cylinder types configured yet.</p>
        }
      </section>

      <!-- Data Grid Section -->
      <section class="dashboard__grid-section">
        <div class="panel">
          <div class="panel-header">
            <h2 class="section-heading">Recent Activity</h2>
          </div>
          <div class="panel-content grid-wrapper">
            <lpg-data-grid
              [rows]="recentActivity()"
              [columns]="activityColumns()"
              [loading]="loading()"
              ariaLabel="Recent platform activity"
            >
            </lpg-data-grid>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .dashboard {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xl);
      }

      /* ---- KPI Cards ---- */
      .dashboard__kpis {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: var(--spacing-lg);
      }

      .kpi-card {
        background: var(--color-surface-raised);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        transition: transform var(--motion-duration-small), box-shadow var(--motion-duration-small);
      }

      .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--elevation-2);
        border-color: var(--color-border-strong);
      }

      .kpi-card__header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
      }

      .kpi-card__title {
        font-size: var(--typography-body-small-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        margin-top: 4px;
      }

      .kpi-card__icon {
        display: flex;
        align-items: center;
        justify-content: center;
        inline-size: 36px;
        block-size: 36px;
        border-radius: var(--radius-md);
        font-size: 16px;
      }

      .kpi-card__icon.bg-red { background: rgba(220, 38, 38, 0.1); color: rgb(220, 38, 38); }
      .kpi-card__icon.bg-blue { background: rgba(37, 99, 235, 0.1); color: rgb(37, 99, 235); }
      .kpi-card__icon.bg-green { background: rgba(22, 163, 74, 0.1); color: rgb(22, 163, 74); }
      .kpi-card__icon.bg-yellow { background: rgba(202, 138, 4, 0.1); color: rgb(202, 138, 4); }
      .kpi-card__icon.bg-purple { background: rgba(126, 34, 206, 0.1); color: rgb(126, 34, 206); }

      .kpi-card__value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--color-text-primary);
        letter-spacing: -0.02em;
        line-height: 1;
        margin-block: var(--spacing-xs);
      }

      /* ---- Charts Section ---- */
      .dashboard__charts {
        display: grid;
        grid-template-columns: 1fr;
        gap: var(--spacing-lg);
      }

      @media (min-width: 1024px) {
        .dashboard__charts {
          grid-template-columns: 2fr 1fr;
        }
      }

      /* ---- Panels ---- */
      .panel {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        background: var(--color-surface-raised);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        box-shadow: var(--elevation-1);
      }

      .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--spacing-sm);
      }

      .panel-header .section-heading {
        margin: 0;
      }

      .panel-content {
        flex: 1;
        min-block-size: 0;
      }

      .chart-container {
        position: relative;
        height: 300px;
        width: 100%;
      }

      /* ---- Section headings outside panels ---- */
      .dashboard__section {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .dashboard__section .section-heading {
        margin: 0;
      }

      .empty-state {
        color: var(--color-text-secondary);
        margin: 0;
      }

      /* ---- Inventory status cards ---- */
      .inventory-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: var(--spacing-md);
      }

      .inventory-card {
        background: var(--color-surface-raised);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        padding: var(--spacing-md);
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .inventory-card__label {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .inventory-card__value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--color-text-primary);
      }

      /* ---- Price cards ---- */
      .price-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: var(--spacing-md);
      }

      .price-card {
        background: var(--color-surface-raised);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        padding: var(--spacing-md);
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .price-card__name {
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-primary);
      }

      .price-card__weight {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }

      .price-card__price {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--color-text-primary);
      }

      /* ---- Grid Section ---- */
      .dashboard__grid-section {
        display: flex;
        flex-direction: column;
      }

      .grid-wrapper {
        flex: 0 0 350px;
        min-height: 350px;
        height: 350px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }
    `,
  ],
})
export class Home implements OnDestroy {
  protected readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
  private readonly el = inject(ElementRef);
  private readonly dashboardService = inject(DashboardService);
  private readonly router = inject(Router);

  protected readonly loading = signal(true);

  // The whole dashboard is one server-composed summary — every KPI, card and
  // chart below is a pure projection of this signal, not an independent
  // fetch. See `GetDashboardSummaryUseCase` on the backend for how it's
  // assembled from Customer/Driver/Vehicle/Warehouse/Inventory/PriceList/
  // Audit repositories in a single request.
  private readonly summary = signal<DashboardSummaryResponse | null>(null);

  protected readonly kpis = signal<KpiData[]>([]);
  protected readonly inventoryCards = signal<InventoryStatusCard[]>([]);
  protected readonly priceCards = signal<CylinderTypePriceCardResponse[]>([]);

  protected readonly recentActivity = signal<DashboardActivityEntryResponse[]>([]);
  protected readonly activityColumns = signal<DataGridColumn<DashboardActivityEntryResponse>[]>([
    {
      field: 'entity_name',
      header: 'Module',
      width: 140,
      valueFormatter: (v) => formatEntityName(v),
      tooltipValueGetter: (v) => String(v ?? ''),
    },
    { field: 'action', header: 'Action', width: 110, cellRenderer: ActionChipCell },
    { field: 'entity_id', header: 'Record', flex: 1, cellRenderer: CopyableIdCell },
    {
      field: 'performed_at',
      header: 'When',
      width: 180,
      valueFormatter: (v) => formatTimestamp(v),
      tooltipValueGetter: (v) => formatTimestamp(v),
    },
  ]);

  // PrimeNG's ChartData<...> generic is impractical to satisfy exactly.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  protected readonly vehicleStatusChartData = signal<any>({});
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  protected readonly inventoryChartData = signal<any>({});
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  protected readonly barChartOptions = signal<any>({});
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  protected readonly doughnutChartOptions = signal<any>({});

  private themeObserver: MutationObserver | null = null;

  constructor() {
    effect(() => {
      if (this.isBrowser) {
        this.initCharts();
      }
    });
    this.loadDashboardData();
  }

  ngOnDestroy() {
    if (this.themeObserver) {
      this.themeObserver.disconnect();
    }
  }

  private initCharts() {
    this.updateChartTheme();

    this.themeObserver = new MutationObserver(() => {
      this.updateChartTheme();
    });
    this.themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    this.themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme'],
    });
  }

  private loadDashboardData(): void {
    this.loading.set(true);

    this.dashboardService
      .getSummary()
      .pipe(catchError(() => of(null)))
      .subscribe((summary) => {
        this.summary.set(summary);
        if (summary) {
          this.recentActivity.set(summary.recent_activity);
          this.inventoryCards.set(
            Object.entries(summary.inventory_by_status).map(([status, quantity]) => ({
              status,
              label: statusLabel(status),
              quantity,
            })),
          );
          this.priceCards.set(summary.price_cards);
        }
        this.rebuildKpis();
        this.updateChartTheme();
        this.loading.set(false);
      });
  }

  private rebuildKpis(): void {
    const summary = this.summary();
    const inventory = summary?.inventory_by_status ?? {};
    const filled = inventory['filled'] ?? 0;
    const needingAttention =
      (inventory['damaged'] ?? 0) + (inventory['leakage'] ?? 0) + (inventory['quarantine'] ?? 0);

    this.kpis.set([
      {
        title: 'Total Customers',
        value: (summary?.customer_count ?? 0).toLocaleString(),
        icon: 'pi pi-users',
        colorClass: 'bg-blue',
      },
      {
        title: 'Drivers',
        value: (summary?.driver_count ?? 0).toLocaleString(),
        icon: 'pi pi-id-card',
        colorClass: 'bg-purple',
      },
      {
        title: 'Fleet Vehicles',
        value: (summary?.vehicle_count ?? 0).toLocaleString(),
        icon: 'pi pi-truck',
        colorClass: 'bg-yellow',
      },
      {
        title: 'Warehouses',
        value: (summary?.warehouse_count ?? 0).toLocaleString(),
        icon: 'pi pi-warehouse',
        colorClass: 'bg-blue',
      },
      {
        title: 'Filled Cylinders',
        value: filled.toLocaleString(),
        icon: 'pi pi-box',
        colorClass: 'bg-green',
      },
      {
        title: 'Cylinders Needing Attention',
        value: needingAttention.toLocaleString(),
        icon: 'pi pi-exclamation-triangle',
        colorClass: 'bg-red',
      },
    ]);
  }

  protected onNewBooking(): void {
    void this.router.navigate(['/orders'], { queryParams: { create: true } });
  }

  protected exportReport(): void {
    const summary = this.summary();
    const rows: string[][] = [
      ['Metric', 'Value'],
      ['Total Customers', String(summary?.customer_count ?? 0)],
      ['Drivers', String(summary?.driver_count ?? 0)],
      ['Fleet Vehicles', String(summary?.vehicle_count ?? 0)],
      ['Warehouses', String(summary?.warehouse_count ?? 0)],
      ['Cylinder Types', String(summary?.cylinder_type_count ?? 0)],
    ];
    for (const [status, qty] of Object.entries(summary?.inventory_by_status ?? {})) {
      rows.push([`Inventory — ${statusLabel(status)}`, String(qty)]);
    }
    for (const [status, qty] of Object.entries(summary?.vehicles_by_status ?? {})) {
      rows.push([`Vehicles — ${status}`, String(qty)]);
    }
    for (const card of summary?.price_cards ?? []) {
      rows.push([`Price — ${card.name} (${card.customer_type})`, card.price ?? 'Not configured']);
    }

    const csv = rows.map((row) => row.map(escapeCsvCell).join(',')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `agency-report-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  private updateChartTheme() {
    // Read the styles from the component's own element to ensure we get the correct inherited theme variables
    const rootStyle = getComputedStyle(this.el.nativeElement);

    let textColor = rootStyle.getPropertyValue('--color-text-primary').trim();
    if (!textColor) textColor = '#111827';

    let textColorSecondary = rootStyle.getPropertyValue('--color-text-secondary').trim();
    if (!textColorSecondary) textColorSecondary = '#6b7280';

    let surfaceBorder = rootStyle.getPropertyValue('--color-border-default').trim();
    if (!surfaceBorder) surfaceBorder = '#e5e7eb';

    const vehicleStatuses = this.summary()?.vehicles_by_status ?? {};
    const vehicleLabels = Object.keys(vehicleStatuses);
    this.vehicleStatusChartData.set({
      labels: vehicleLabels.length > 0 ? vehicleLabels : ['No vehicles yet'],
      datasets: [
        {
          label: 'Vehicles',
          data: vehicleLabels.length > 0 ? vehicleLabels.map((s) => vehicleStatuses[s]) : [0],
          backgroundColor: 'rgb(37, 99, 235)',
          borderRadius: 4,
        },
      ],
    });

    this.barChartOptions.set({
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: textColorSecondary }, grid: { display: false } },
        y: {
          ticks: { color: textColorSecondary, stepSize: 1 },
          grid: { color: surfaceBorder, drawBorder: false },
          beginAtZero: true,
        },
      },
    });

    const inventoryStatuses = this.summary()?.inventory_by_status ?? {};
    const inventoryLabels = Object.keys(inventoryStatuses);
    const statusColors: Record<string, string> = {
      filled: 'rgb(37, 99, 235)',
      empty: 'rgb(156, 163, 175)',
      damaged: 'rgb(220, 38, 38)',
      leakage: 'rgb(202, 138, 4)',
      quarantine: 'rgb(126, 34, 206)',
      repair: 'rgb(13, 148, 136)',
      scrap: 'rgb(75, 85, 99)',
    };
    this.inventoryChartData.set({
      labels: inventoryLabels.length > 0 ? inventoryLabels : ['No inventory yet'],
      datasets: [
        {
          data: inventoryLabels.length > 0 ? inventoryLabels.map((s) => inventoryStatuses[s]) : [1],
          backgroundColor:
            inventoryLabels.length > 0
              ? inventoryLabels.map((s) => statusColors[s] ?? 'rgb(156, 163, 175)')
              : ['rgb(229, 231, 235)'],
          borderWidth: 0,
        },
      ],
    });

    this.doughnutChartOptions.set({
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: textColor, padding: 20, usePointStyle: true },
        },
      },
    });
  }
}
