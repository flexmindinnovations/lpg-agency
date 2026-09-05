import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
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
  ActivityListComponent,
  type ActivityItem,
  type ActivityStatusTone,
  EmptyStateComponent,
  formatEntityName,
  formatTimestamp,
  HasPermissionDirective,
  PageHeaderComponent,
  SectionCardComponent,
  SkeletonComponent,
  StatCardComponent,
  type StatTone,
} from '@lpg/shared/ui';
import {
  DashboardService,
  type CylinderTypePriceCardResponse,
  type DashboardActivityEntryResponse,
  DashboardSummaryResponse,
  WebSocketService,
} from '@lpg/shared/data-access';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

interface KpiData {
  title: string;
  value: string;
  icon: string;
  tone: StatTone;
  permission?: string;
}

const ACTION_ICON: Record<string, string> = {
  create: 'pi pi-plus-circle',
  update: 'pi pi-pencil',
  delete: 'pi pi-trash',
};

const ACTION_TONE: Record<string, ActivityStatusTone> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
};

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
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ButtonDirective, ButtonIcon, ButtonLabel, ChartModule, HasPermissionDirective, PageHeaderComponent, SectionCardComponent, StatCardComponent, ActivityListComponent, EmptyStateComponent, SkeletonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dashboard">
      <ng-template lpgHeaderTitlePortal>
        <lpg-page-header
          title="Agency Overview"
          subtitle="Live summary of your agency's operational data across every module."
        />
      </ng-template>
      <ng-template lpgHeaderPortal>
        <div class="dashboard__actions">
          <button
            *lpgHasPermission="'reports:read'"
            pButton
            severity="secondary"
            [disabled]="loading()"
            (click)="exportReport()"
          >
            <i pButtonIcon class="pi pi-download"></i>
            <span pButtonLabel>Export Report</span>
          </button>
          <button *lpgHasPermission="'orders:create'" pButton type="button" (click)="onNewBooking()">
            <i pButtonIcon class="pi pi-plus"></i>
            <span pButtonLabel>New Booking</span>
          </button>
        </div>
      </ng-template>

      <!-- KPI Section -->
      <section class="dashboard__kpis">
        @for (kpi of kpis(); track kpi.title; let i = $index) {
          <lpg-stat-card
            *lpgHasPermission="kpi.permission"
            class="animate-fade-up"
            [style.--lpg-stagger-index]="i"
            [label]="kpi.title"
            [value]="kpi.value"
            [icon]="kpi.icon"
            [tone]="kpi.tone"
            [loading]="loading()"
          />
        }
      </section>

      <!-- Charts Section -->
      <section class="dashboard__charts">
        <lpg-section-card *lpgHasPermission="'vehicles:read'" heading="Fleet Status">
          <div class="chart-container">
            @if (isBrowser) {
              <p-chart type="bar" [data]="vehicleStatusChartData()" [options]="barChartOptions()"></p-chart>
            }
          </div>
        </lpg-section-card>
        <lpg-section-card *lpgHasPermission="'inventory:read'" heading="Cylinder Inventory (All Locations)">
          <div class="chart-container">
            @if (isBrowser) {
              <p-chart type="doughnut" [data]="inventoryChartData()" [options]="doughnutChartOptions()"></p-chart>
            }
          </div>
        </lpg-section-card>
      </section>

      <!-- Inventory Detail Cards -->
      <lpg-section-card *lpgHasPermission="'inventory:read'" heading="Inventory by Status">
        @if (inventoryCards().length > 0) {
          <div class="mini-cards">
            @for (card of inventoryCards(); track card.status) {
              <div class="mini-card">
                <span class="mini-card__label">{{ card.label }}</span>
                <span class="mini-card__value">{{ card.quantity.toLocaleString() }}</span>
              </div>
            }
          </div>
        } @else if (!loading()) {
          <lpg-empty-state title="No inventory activity yet" description="Cylinder movements will appear here once stock is recorded." />
        }
      </lpg-section-card>

      <!-- Price Cards -->
      <lpg-section-card *lpgHasPermission="'tenant:configure'" heading="Cylinder Pricing (Domestic)">
        @if (priceCards().length > 0) {
          <div class="mini-cards">
            @for (card of priceCards(); track card.cylinder_type_id) {
              <div class="mini-card">
                <span class="mini-card__label">{{ card.name }} · {{ card.weight_kg }} kg</span>
                <span class="mini-card__value">
                  {{ card.price ? '₹' + card.price : 'Not configured' }}
                </span>
              </div>
            }
          </div>
        } @else if (!loading()) {
          <lpg-empty-state title="No cylinder types configured yet" description="Add cylinder types and a price list to see pricing here." />
        }
      </lpg-section-card>

      <!-- Recent Activity -->
      <lpg-section-card *lpgHasPermission="'audit:read'" heading="Recent Activity">
        @if (activityItems().length > 0) {
          <lpg-activity-list [items]="activityItems()" />
        } @else if (loading()) {
          <lpg-skeleton variant="text" [lines]="4" />
        } @else {
          <lpg-empty-state title="No recent activity" description="Actions across the platform will show up here." />
        }
      </lpg-section-card>
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

      .dashboard__actions {
        display: flex;
        gap: var(--spacing-sm);
      }

      .dashboard__kpis {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: var(--spacing-lg);
      }

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

      .chart-container {
        position: relative;
        height: 300px;
        width: 100%;
      }

      /* Compact label/value tiles inside a section card (inventory, pricing). */
      .mini-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: var(--spacing-md);
      }

      .mini-card {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: var(--spacing-md);
        background: var(--color-surface-overlay);
        border-radius: var(--radius-input);
      }

      .mini-card__label {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .mini-card__value {
        font-size: var(--typography-heading3-font-size);
        font-weight: 700;
        color: var(--color-text-primary);
      }
    `,
  ],
})
export class Home implements OnDestroy {
  protected readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
  private readonly el = inject(ElementRef);
  private readonly dashboardService = inject(DashboardService);
  private readonly router = inject(Router);
  private readonly wsService = inject(WebSocketService);

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

  /** The "Recent Activity" list (doc §17) — a lighter projection than the
   *  full audit grid at /admin/audit-log. */
  protected readonly activityItems = computed<ActivityItem[]>(() =>
    this.recentActivity()
      .slice(0, 8)
      .map((entry) => ({
        time: formatTimestamp(entry.performed_at),
        icon: ACTION_ICON[entry.action] ?? 'pi pi-circle',
        title: formatEntityName(entry.entity_name),
        description: entry.entity_id ? String(entry.entity_id).slice(0, 8).toUpperCase() : undefined,
        status: entry.action ? entry.action.charAt(0).toUpperCase() + entry.action.slice(1) : undefined,
        statusTone: ACTION_TONE[entry.action] ?? 'neutral',
      })),
  );

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

    this.wsService.subscribeTo('dashboard');
    this.wsService.on('dashboard.metrics_stale')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        this.loadDashboardData();
      });
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
        tone: 'info',
        permission: 'customers:read'
      },
      {
        title: 'Drivers',
        value: (summary?.driver_count ?? 0).toLocaleString(),
        icon: 'pi pi-id-card',
        tone: 'info',
        permission: 'drivers:read'
      },
      {
        title: 'Fleet Vehicles',
        value: (summary?.vehicle_count ?? 0).toLocaleString(),
        icon: 'pi pi-truck',
        tone: 'warning',
        permission: 'vehicles:read'
      },
      {
        title: 'Warehouses',
        value: (summary?.warehouse_count ?? 0).toLocaleString(),
        icon: 'pi pi-warehouse',
        tone: 'primary',
        permission: 'tenant:configure'
      },
      {
        title: 'Filled Cylinders',
        value: filled.toLocaleString(),
        icon: 'pi pi-box',
        tone: 'success',
        permission: 'inventory:read'
      },
      {
        title: 'Cylinders Needing Attention',
        value: needingAttention.toLocaleString(),
        icon: 'pi pi-exclamation-triangle',
        tone: 'danger',
        permission: 'inventory:read'
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

    let brandPrimary = rootStyle.getPropertyValue('--color-action-primary').trim();
    if (!brandPrimary) brandPrimary = '#162b66';

    const vehicleStatuses = this.summary()?.vehicles_by_status ?? {};
    const vehicleLabels = Object.keys(vehicleStatuses);
    this.vehicleStatusChartData.set({
      labels: vehicleLabels.length > 0 ? vehicleLabels : ['No vehicles yet'],
      datasets: [
        {
          label: 'Vehicles',
          data: vehicleLabels.length > 0 ? vehicleLabels.map((s) => vehicleStatuses[s]) : [0],
          backgroundColor: brandPrimary,
          borderRadius: 8,
          maxBarThickness: 56,
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

    let statusSuccess = rootStyle.getPropertyValue('--color-status-success').trim();
    if (!statusSuccess) statusSuccess = '#16a34a';
    let statusWarning = rootStyle.getPropertyValue('--color-status-warning').trim();
    if (!statusWarning) statusWarning = '#d97706';
    let statusDanger = rootStyle.getPropertyValue('--color-status-danger').trim();
    if (!statusDanger) statusDanger = '#dc2626';
    let flameOrange = rootStyle.getPropertyValue('--primitive-color-flame-orange-500').trim();
    if (!flameOrange) flameOrange = '#ff6f12';
    let neutral = rootStyle.getPropertyValue('--color-text-disabled').trim();
    if (!neutral) neutral = '#9ca3af';

    const inventoryStatuses = this.summary()?.inventory_by_status ?? {};
    const inventoryLabels = Object.keys(inventoryStatuses);
    const statusColors: Record<string, string> = {
      filled: brandPrimary,
      empty: neutral,
      damaged: statusDanger,
      leakage: statusWarning,
      quarantine: flameOrange,
      repair: statusSuccess,
      scrap: surfaceBorder,
    };
    this.inventoryChartData.set({
      labels: inventoryLabels.length > 0 ? inventoryLabels : ['No inventory yet'],
      datasets: [
        {
          data: inventoryLabels.length > 0 ? inventoryLabels.map((s) => inventoryStatuses[s]) : [1],
          backgroundColor:
            inventoryLabels.length > 0
              ? inventoryLabels.map((s) => statusColors[s] ?? neutral)
              : [surfaceBorder],
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
