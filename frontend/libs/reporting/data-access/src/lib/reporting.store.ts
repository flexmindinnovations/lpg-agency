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
  total_invoices: number;
  total_revenue: number;
  total_tax: number;
}

export interface DriverPerformanceRecord {
  driver_id: string;
  date: string;
  total_stops: number;
  delivered_stops: number;
  cash_accuracy: number;
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
  dailySales: DailySalesRecord[];
  driverPerformance: DriverPerformanceRecord[];
  customerConsumption: CustomerConsumptionRecord[];
  gstFiling: GstFilingRecord[];
  loading: boolean;
  error: string | null;
}

const initialState: ReportingState = {
  dailySales: [],
  driverPerformance: [],
  customerConsumption: [],
  gstFiling: [],
  loading: false,
  error: null,
};

/**
 * The message shown when a report fails to load. HTTP errors reach here as
 * the app's normalised `AppError` (`problemDetailsInterceptor`), which has a
 * `detail`, not a `message` — reading `.message` gave `undefined`, so a 500
 * rendered as an empty "No Rows To Show" report instead of an error (QA
 * DA-15). This lib may not import `@lpg/shared/data-access`'s
 * `errorMessageFor`, hence the small local reader.
 */
export function loadErrorMessage(error: unknown): string {
  const fallback = 'The report could not be loaded. Please try again.';
  if (typeof error !== 'object' || error === null) return fallback;
  const { detail, message, isNetworkError } = error as {
    detail?: unknown;
    message?: unknown;
    isNetworkError?: unknown;
  };
  if (isNetworkError === true) return 'Cannot reach the server. Check your connection and try again.';
  if (typeof detail === 'string' && detail) return detail;
  if (typeof message === 'string' && message) return message;
  return fallback;
}

export const ReportingStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withMethods((store, http = inject(HttpClient), apiBaseUrl = inject(API_BASE_URL)) => ({
    loadDailySales: rxMethod<{ startDate: string; endDate: string }>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(({ startDate, endDate }) =>
          http
            .get<DailySalesRecord[]>(
              `${apiBaseUrl}/api/v1/reporting/sales?start_date=${startDate}&end_date=${endDate}`,
            )
            .pipe(
              tapResponse({
                next: (dailySales) => patchState(store, { dailySales, loading: false }),
                error: (error: unknown) =>
                  patchState(store, { error: loadErrorMessage(error), loading: false }),
              }),
            ),
        ),
      ),
    ),
    loadDriverPerformance: rxMethod<{ startDate: string; endDate: string }>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(({ startDate, endDate }) =>
          http
            .get<DriverPerformanceRecord[]>(
              `${apiBaseUrl}/api/v1/reporting/drivers?start_date=${startDate}&end_date=${endDate}`,
            )
            .pipe(
              tapResponse({
                next: (driverPerformance) =>
                  patchState(store, { driverPerformance, loading: false }),
                error: (error: unknown) =>
                  patchState(store, { error: loadErrorMessage(error), loading: false }),
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
                patchState(store, { error: loadErrorMessage(error), loading: false }),
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
                patchState(store, { error: loadErrorMessage(error), loading: false }),
            }),
          ),
        ),
      ),
    ),
  })),
);
