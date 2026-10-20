import { inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { signalStore, withState, withMethods, patchState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, switchMap, tap } from 'rxjs';
import { tapResponse } from '@ngrx/operators';
import { API_BASE_URL } from '@lpg/shared/util';

export interface DailySalesRecord {
  sale_date: string;
  branch_id: string | null;
  branch_name: string | null;
  total_invoices: number;
  taxable_value: string;
  total_revenue: string;
  total_tax: string;
}

export interface DriverPerformanceRecord {
  driver_id: string;
  driver_name: string;
  employee_code: string | null;
  branch_name: string | null;
  date: string;
  total_stops: number;
  delivered_stops: number;
  failed_stops: number;
  cash_expected: string;
  cash_handed_over: string | null;
  /** Handed over ÷ expected; `null` when no cash was due. */
  cash_accuracy: number | null;
}

export interface GstTaxTotals {
  taxable_value: string;
  cgst: string;
  sgst: string;
  igst: string;
  total_tax: string;
}

export interface Gstr1InvoiceRow {
  invoice_id: string;
  invoice_number: string | null;
  invoice_date: string;
  customer_name: string;
  customer_gstin: string | null;
  invoice_value: string;
  place_of_supply: string;
  rate_percent: string;
  totals: GstTaxTotals;
}

export interface Gstr1Report {
  start_date: string;
  end_date: string;
  invoice_count: number;
  b2b: Gstr1InvoiceRow[];
  b2cl: Gstr1InvoiceRow[];
  b2cs: { place_of_supply: string; rate_percent: string; totals: GstTaxTotals }[];
  hsn: { hsn_code: string; rate_percent: string; quantity: number; totals: GstTaxTotals }[];
  totals: GstTaxTotals;
}

/** Shared by the date-ranged report tabs, so switching tabs keeps them. */
export interface ReportFilter {
  /** IST calendar days, `YYYY-MM-DD`, inclusive. */
  startDate: string;
  endDate: string;
  branchId: string | null;
}

/** Today in India, as `YYYY-MM-DD` — not `toISOString()`, which is UTC
 * and gives yesterday's date before 05:30 IST (DA-12). */
export function istDate(offsetDays = 0): string {
  const date = new Date(Date.now() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(date);
}

export interface CustomerConsumptionRecord {
  customer_id: string;
  customer_name: string;
  avg_refill_interval_days: number;
}

export interface GstFilingRecord {
  filing_period: string;
  total_gst: number;
}

interface ReportingState {
  filter: ReportFilter;
  gstr1: Gstr1Report | null;
  dailySales: DailySalesRecord[];
  driverPerformance: DriverPerformanceRecord[];
  customerConsumption: CustomerConsumptionRecord[];
  gstFiling: GstFilingRecord[];
  loading: boolean;
  error: string | null;
}

const initialState: ReportingState = {
  filter: { startDate: istDate(-29), endDate: istDate(), branchId: null },
  gstr1: null,
  dailySales: [],
  driverPerformance: [],
  customerConsumption: [],
  gstFiling: [],
  loading: false,
  error: null,
};

function rangeParams(filter: ReportFilter): Record<string, string> {
  const params: Record<string, string> = {
    start_date: filter.startDate,
    end_date: filter.endDate,
  };
  if (filter.branchId) params['branch_id'] = filter.branchId;
  return params;
}

/** The backend's own Problem Details text (e.g. "Choose a range of at most
 * one year.") when there is one. */
function messageOf(error: unknown): string {
  const detail = (error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  const message = (error as { message?: unknown } | null)?.message;
  return typeof message === 'string' && message ? message : "The report couldn't be loaded.";
}

export const ReportingStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withMethods((store, http = inject(HttpClient), apiBaseUrl = inject(API_BASE_URL)) => ({
    setFilter(filter: Partial<ReportFilter>): void {
      patchState(store, { filter: { ...store.filter(), ...filter } });
    },
    loadDailySales: rxMethod<ReportFilter>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap((filter) =>
          http
            .get<DailySalesRecord[]>(`${apiBaseUrl}/api/v1/reporting/sales`, {
              params: rangeParams(filter),
            })
            .pipe(
              tapResponse({
                next: (dailySales) => patchState(store, { dailySales, loading: false }),
                error: (error: unknown) =>
                  patchState(store, { error: messageOf(error), loading: false }),
              }),
            ),
        ),
      ),
    ),
    loadGstr1: rxMethod<ReportFilter>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap((filter) =>
          http
            .get<Gstr1Report>(`${apiBaseUrl}/api/v1/reporting/gst/gstr1`, {
              params: { start_date: filter.startDate, end_date: filter.endDate },
            })
            .pipe(
              tapResponse({
                next: (gstr1) => patchState(store, { gstr1, loading: false }),
                error: (error: unknown) =>
                  patchState(store, { error: messageOf(error), loading: false }),
              }),
            ),
        ),
      ),
    ),
    loadDriverPerformance: rxMethod<ReportFilter>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap((filter) =>
          http
            .get<DriverPerformanceRecord[]>(`${apiBaseUrl}/api/v1/reporting/drivers`, {
              params: rangeParams(filter),
            })
            .pipe(
              tapResponse({
                next: (driverPerformance) =>
                  patchState(store, { driverPerformance, loading: false }),
                error: (error: unknown) =>
                  patchState(store, { error: messageOf(error), loading: false }),
              }),
            ),
        ),
      ),
    ),
    loadCustomerConsumption: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          http.get<CustomerConsumptionRecord[]>(`${apiBaseUrl}/api/v1/reporting/consumption`).pipe(
            tapResponse({
              next: (customerConsumption) =>
                patchState(store, { customerConsumption, loading: false }),
              error: (error: unknown) =>
                patchState(store, { error: messageOf(error), loading: false }),
            }),
          ),
        ),
      ),
    ),
    loadGstFiling: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          http.get<GstFilingRecord[]>(`${apiBaseUrl}/api/v1/reporting/gst`).pipe(
            tapResponse({
              next: (gstFiling) => patchState(store, { gstFiling, loading: false }),
              error: (error: unknown) =>
                patchState(store, { error: messageOf(error), loading: false }),
            }),
          ),
        ),
      ),
    ),
  })),
);
