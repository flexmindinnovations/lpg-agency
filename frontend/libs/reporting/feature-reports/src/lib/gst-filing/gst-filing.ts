import { Component, computed, inject, viewChildren } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatCurrencyInr,
  formatReportDate,
} from '@lpg/shared/ui';
import {
  ReportingStore,
  type Gstr1InvoiceRow,
  type Gstr1Report,
  type ReportFilter,
} from '@lpg/reporting/data-access';
import { ReportFilters } from '../report-filters/report-filters';

type B2csRow = Gstr1Report['b2cs'][number];
type HsnRow = Gstr1Report['hsn'][number];

/** A tax-head column read from the row's nested `totals`. */
function money<T>(path: (row: T) => string): Partial<DataGridColumn<T>> {
  return {
    numeric: true,
    sortable: false,
    valueFormatter: (_: unknown, row: T) => formatCurrencyInr(path(row)),
  };
}

const rate = (v: unknown): string => `${Number(v)}%`;

/**
 * GSTR-1 style outward supplies for a period (DA-12): B2B (table 4A),
 * B2C large (5), B2C small (7) and the HSN summary (12), with the
 * CGST / SGST / IGST split. Branch is not a filter here — a return is
 * filed per GSTIN, not per branch.
 */
@Component({
  selector: 'lib-gst-filing',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent, ReportFilters],
  templateUrl: './gst-filing.html',
  styleUrl: './gst-filing.css',
})
export class GstFiling {
  store = inject(ReportingStore);
  private readonly grids = viewChildren(DataGridComponent);

  protected readonly report = computed(() => this.store.gstr1());
  protected readonly formatCurrencyInr = formatCurrencyInr;

  protected readonly invoiceColumns: DataGridColumn<Gstr1InvoiceRow>[] = [
    {
      field: 'invoice_number',
      header: 'Invoice #',
      valueFormatter: (v) => (v as string | null) ?? 'Not numbered',
    },
    { field: 'invoice_date', header: 'Date', valueFormatter: formatReportDate },
    { field: 'customer_name', header: 'Customer', flex: 2 },
    {
      field: 'customer_gstin',
      header: 'GSTIN',
      valueFormatter: (v) => (v as string | null) ?? '—',
    },
    { field: 'place_of_supply', header: 'Place of supply' },
    { field: 'rate_percent', header: 'Rate', numeric: true, valueFormatter: rate },
    {
      field: 'taxable',
      header: 'Taxable value',
      ...money((r: Gstr1InvoiceRow) => r.totals.taxable_value),
    },
    { field: 'cgst', header: 'CGST', ...money((r: Gstr1InvoiceRow) => r.totals.cgst) },
    { field: 'sgst', header: 'SGST', ...money((r: Gstr1InvoiceRow) => r.totals.sgst) },
    { field: 'igst', header: 'IGST', ...money((r: Gstr1InvoiceRow) => r.totals.igst) },
    {
      field: 'invoice_value',
      header: 'Invoice value',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
  ];

  protected readonly b2csColumns: DataGridColumn<B2csRow>[] = [
    { field: 'place_of_supply', header: 'Place of supply', flex: 2 },
    { field: 'rate_percent', header: 'Rate', numeric: true, valueFormatter: rate },
    { field: 'taxable', header: 'Taxable value', ...money((r: B2csRow) => r.totals.taxable_value) },
    { field: 'cgst', header: 'CGST', ...money((r: B2csRow) => r.totals.cgst) },
    { field: 'sgst', header: 'SGST', ...money((r: B2csRow) => r.totals.sgst) },
    { field: 'igst', header: 'IGST', ...money((r: B2csRow) => r.totals.igst) },
  ];

  protected readonly hsnColumns: DataGridColumn<HsnRow>[] = [
    { field: 'hsn_code', header: 'HSN' },
    { field: 'rate_percent', header: 'Rate', numeric: true, valueFormatter: rate },
    { field: 'quantity', header: 'Quantity (NOS)', numeric: true },
    { field: 'taxable', header: 'Taxable value', ...money((r: HsnRow) => r.totals.taxable_value) },
    { field: 'cgst', header: 'CGST', ...money((r: HsnRow) => r.totals.cgst) },
    { field: 'sgst', header: 'SGST', ...money((r: HsnRow) => r.totals.sgst) },
    { field: 'igst', header: 'IGST', ...money((r: HsnRow) => r.totals.igst) },
  ];

  protected load(filter: ReportFilter): void {
    this.store.loadGstr1(filter);
  }

  /** One CSV per GSTR-1 table, in the order they appear. */
  protected exportCsv(): void {
    const { startDate, endDate } = this.store.filter();
    const names = ['b2b', 'b2cl', 'b2cs', 'hsn'];
    this.grids().forEach((grid, index) =>
      grid.exportCsv(`gstr1-${names[index] ?? index}-${startDate}-to-${endDate}`),
    );
  }
}
