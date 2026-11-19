import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  EmptyStateComponent,
  formatCurrencyInr,
  HasPermissionDirective,
  PageHeaderComponent,
  SectionCardComponent,
  SkeletonComponent,
  StatCardComponent,
  type StatTone,
} from '@lpg/shared/ui';
import { addDays } from './dashboard-dates';
import { DashboardData, type WidgetData } from './dashboard-data';
import {
  attentionItems,
  compactInr,
  deliveredByDay,
  percentChange,
  revenueByDay,
  series,
  type AttentionSeverity,
  type Delta,
} from './dashboard-model';
import { HomeCharts } from './home-charts';
import { SetupChecklist } from './setup-checklist/setup-checklist';

interface Kpi {
  key: string;
  label: string;
  value: string;
  icon: string;
  tone: StatTone;
  route: string;
  permission?: string;
  loading: boolean;
  delta?: Delta | null;
  trend?: readonly number[];
}

const SEVERITY_ICON: Record<AttentionSeverity, string> = {
  critical: 'pi pi-exclamation-circle',
  warning: 'pi pi-exclamation-triangle',
  info: 'pi pi-info-circle',
};

/** Whether a widget has nothing to show yet (first load, no value kept). */
function pending(widget: WidgetData<unknown>): boolean {
  return widget.data() === null && widget.status() === 'loading';
}

/**
 * Home: what needs attention now, how today compares with a normal day, then
 * the charts. Charts come first, straight under the setup card; each chart
 * loads into its already-sized card (see `HomeCharts`).
 */
@Component({
  selector: 'lpg-home',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    RouterLink,
    HasPermissionDirective,
    PageHeaderComponent,
    SectionCardComponent,
    StatCardComponent,
    EmptyStateComponent,
    SkeletonComponent,
    SetupChecklist,
    HomeCharts,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dashboard">
      <ng-template lpgHeaderTitlePortal>
        <lpg-page-header title="Agency Overview" subtitle="Today at your agency." />
      </ng-template>

      <lpg-setup-checklist />

      <lpg-home-charts />

      <lpg-section-card heading="Needs attention">
        <div class="attention" [style.min-block-size.px]="attentionHeight()">
          @if (attention().length > 0) {
            <ul class="attention__list">
              @for (item of attention(); track item.key; let i = $index) {
                <li
                  class="attention__row"
                  [class.attention__row--enter]="!data.isRevisit"
                  [style.--row-index]="i"
                >
                  <a class="attention__link" [routerLink]="item.route">
                    <i
                      class="attention__icon attention__icon--{{ item.severity }} {{
                        icon[item.severity]
                      }}"
                      aria-hidden="true"
                    ></i>
                    <span class="attention__count">{{ item.count.toLocaleString('en-IN') }}</span>
                    <span class="attention__text">
                      {{ item.text }}
                      @if (item.detail) {
                        <span class="attention__detail">{{ item.detail }}</span>
                      }
                    </span>
                    <i class="pi pi-arrow-right attention__go" aria-hidden="true"></i>
                  </a>
                </li>
              }
            </ul>
          } @else if (data.operations.status() === 'loading') {
            <lpg-skeleton variant="text" [lines]="3" />
          } @else if (data.operations.status() === 'error') {
            <lpg-empty-state
              tone="error"
              title="Today's figures could not be loaded"
              description="They will retry automatically. The rest of the page is unaffected."
            />
          } @else {
            <lpg-empty-state
              icon="pi pi-check-circle"
              title="Nothing needs you right now"
              description="Failed deliveries, approvals, low stock and held invoices show here when they come up."
            />
          }
        </div>
      </lpg-section-card>

      <section class="dashboard__kpis" aria-label="Key figures">
        @for (kpi of kpis(); track kpi.key) {
          <lpg-stat-card
            *lpgHasPermission="kpi.permission"
            [label]="kpi.label"
            [value]="kpi.value"
            [icon]="kpi.icon"
            [tone]="kpi.tone"
            [route]="kpi.route"
            [loading]="kpi.loading"
            [delta]="kpi.delta?.text ?? ''"
            [deltaDirection]="kpi.delta?.direction ?? null"
            [caption]="kpi.delta ? 'vs same day last week' : ''"
            [trend]="kpi.trend ?? []"
            [animateTrend]="!data.isRevisit"
          />
        }
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

      /* Six tiles: 2 across on a phone, 3 on a tablet, one row of 6 when there
         is room, so the last row is never a stray pair. Sized by the page's
         own width, not the window's, so the open sidebar is accounted for. */
      .dashboard {
        container-type: inline-size;
      }

      .dashboard__kpis {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        grid-auto-rows: 1fr;
        gap: var(--spacing-lg);
      }

      @container (min-width: 640px) {
        .dashboard__kpis {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }

      @container (min-width: 1040px) {
        .dashboard__kpis {
          grid-template-columns: repeat(6, minmax(0, 1fr));
        }
      }

      /* ---- Needs attention ---- */

      .attention__list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
        gap: var(--spacing-xs) var(--spacing-lg);
      }

      /* Rows slide in the first time Home is shown, not on every visit. */
      .attention__row--enter {
        animation: attention-in var(--motion-duration-medium) var(--motion-easing-emphasized) both;
        animation-delay: calc(var(--row-index, 0) * 45ms);
      }

      @keyframes attention-in {
        from {
          opacity: 0;
          transform: translateY(6px);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .attention__row--enter {
          animation: none;
        }
      }

      .attention__link {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-input);
        color: var(--color-text-primary);
        text-decoration: none;
        transition: background-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .attention__link:hover {
        background: var(--color-surface-overlay);
      }

      .attention__link:focus-visible {
        outline: var(--component-focus-ring-width) solid var(--component-focus-ring-color);
        outline-offset: -2px;
      }

      .attention__icon {
        font-size: var(--icon-size-md);
        flex-shrink: 0;
      }

      .attention__icon--critical {
        color: var(--color-status-danger);
      }

      .attention__icon--warning {
        color: var(--color-status-warning);
      }

      .attention__icon--info {
        color: var(--color-status-info);
      }

      .attention__count {
        min-inline-size: 2ch;
        font-size: var(--typography-heading3-font-size);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
      }

      .attention__text {
        flex: 1;
        min-inline-size: 0;
        font-size: var(--typography-secondary-font-size);
      }

      .attention__detail {
        display: block;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .attention__go {
        font-size: 11px;
        color: var(--color-text-secondary);
        opacity: 0;
        transform: translateX(-4px);
        transition:
          opacity var(--motion-duration-small) var(--motion-easing-standard),
          transform var(--motion-duration-small) var(--motion-easing-standard);
      }

      .attention__link:hover .attention__go,
      .attention__link:focus-visible .attention__go {
        opacity: 1;
        transform: none;
      }
    `,
  ],
})
export class Home {
  protected readonly data = inject(DashboardData);
  protected readonly icon = SEVERITY_ICON;

  constructor() {
    // Show what was fetched last time, refresh only what is stale, and keep
    // today's figures live while Home is open.
    inject(DestroyRef).onDestroy(this.data.connect());
  }

  protected readonly attention = computed(() => {
    const ops = this.data.operations.data();
    return ops ? attentionItems(ops, formatCurrencyInr) : [];
  });

  /** Holds the card's height while loading so the KPI tiles below do not jump. */
  protected readonly attentionHeight = computed(() => {
    const rows = this.attention().length;
    return rows > 0 ? 0 : 104;
  });

  protected readonly kpis = computed<Kpi[]>(() => {
    const d = this.data;
    const today = d.today;
    const lastWeek = addDays(today, -7);
    const week = [addDays(today, -6), today] as const;

    const ops = d.operations.data();
    const drivers = d.drivers.data();
    const sales = d.sales.data();
    const summary = d.summary.data();
    const rating = d.rating.data();

    const delivered = drivers ? deliveredByDay(drivers) : null;
    const revenue = sales ? revenueByDay(sales) : null;

    const tiles: Kpi[] = [
      {
        key: 'delivered',
        label: 'Delivered today',
        value: (ops?.orders.delivered_today ?? 0).toLocaleString('en-IN'),
        icon: 'pi pi-check-circle',
        tone: 'success',
        route: '/orders',
        loading: pending(d.operations),
        delta: delivered
          ? percentChange(delivered.get(today) ?? 0, delivered.get(lastWeek) ?? 0)
          : null,
        trend: delivered ? series(delivered, ...week) : [],
      },
      {
        key: 'revenue',
        label: 'Revenue today',
        value: compactInr(revenue?.get(today) ?? 0),
        icon: 'pi pi-indian-rupee',
        tone: 'primary',
        route: '/invoices',
        loading: pending(d.sales),
        delta: revenue ? percentChange(revenue.get(today) ?? 0, revenue.get(lastWeek) ?? 0) : null,
        trend: revenue ? series(revenue, ...week) : [],
      },
      {
        key: 'overdue',
        label: ops?.invoices ? `Overdue over ${ops.payment_terms_days} days` : 'Overdue invoices',
        value: compactInr(Number(ops?.invoices?.overdue_amount ?? 0)),
        icon: 'pi pi-exclamation-circle',
        tone: 'danger',
        route: '/invoices',
        loading: pending(d.operations),
      },
      {
        key: 'filled',
        label: 'Filled cylinders',
        value: (summary?.inventory_by_status['filled'] ?? 0).toLocaleString('en-IN'),
        icon: 'pi pi-box',
        tone: 'info',
        route: '/inventory',
        permission: 'inventory:read',
        loading: pending(d.summary),
      },
      {
        key: 'rating',
        label: 'Delivery-time rating',
        value:
          typeof rating?.overall_stars === 'number'
            ? `${rating.overall_stars} ${rating.overall_stars === 1 ? 'star' : 'stars'}`
            : '—',
        icon: 'pi pi-star',
        tone: 'warning',
        route: '/reports/tdt-rating',
        loading: pending(d.rating),
      },
      {
        key: 'complaints',
        label: 'Open complaints',
        value: (ops?.open_complaints ?? 0).toLocaleString('en-IN'),
        icon: 'pi pi-comments',
        tone: 'warning',
        route: '/complaints',
        loading: pending(d.operations),
      },
    ];

    // Once loaded, leave out tiles the caller may not see (server returns null / 403).
    return tiles.filter(
      (tile) =>
        !(tile.key === 'overdue' && d.operations.status() === 'ready' && ops?.invoices == null) &&
        !(tile.key === 'revenue' && !d.sales.visible()) &&
        !(tile.key === 'rating' && !d.rating.visible()),
    );
  });
}
