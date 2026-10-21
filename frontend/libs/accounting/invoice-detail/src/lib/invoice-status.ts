import { toSentenceCase, type ChipSeverity } from '@lpg/shared/ui';

/** Chip colour per invoice status, shared by the Invoices list, the invoice
 *  drawer and the order page so one status always looks the same. */
export const INVOICE_STATUS_SEVERITY: Record<string, ChipSeverity> = {
  draft: 'secondary',
  issued: 'warn',
  partially_paid: 'warn',
  paid: 'success',
  cancelled: 'danger',
  refunded: 'danger',
};

/** An issued invoice is one nobody has paid yet; staff call it "Unpaid". */
export const INVOICE_STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  issued: 'Unpaid',
  partially_paid: 'Partially paid',
  paid: 'Paid',
  cancelled: 'Cancelled',
  refunded: 'Refunded',
};

export function invoiceStatusLabel(status: string): string {
  return INVOICE_STATUS_LABEL[status] ?? toSentenceCase(status);
}

export function invoiceStatusSeverity(status: string): ChipSeverity {
  return INVOICE_STATUS_SEVERITY[status] ?? 'secondary';
}
