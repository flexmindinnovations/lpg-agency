/**
 * Reading the price list (append-only, D-42): which price is in force, what a
 * table cell says about it, and the words around a price field.
 */
import type { PriceListEntryResponse } from '@lpg/shared/data-access';
import { formatCurrencyInr, toSentenceCase } from '@lpg/shared/ui';

export const CUSTOMER_TYPES = ['domestic', 'commercial', 'industrial', 'government'] as const;

export type CustomerType = (typeof CUSTOMER_TYPES)[number];

export const customerTypeOptions = CUSTOMER_TYPES.map((value) => ({
  value,
  label: toSentenceCase(value),
}));

/** Who a cylinder of this type is usually sold to. */
export function defaultCustomerType(category: string | null | undefined): CustomerType {
  return category === 'commercial' ? 'commercial' : 'domestic';
}

/** The GST rate LPG usually carries; the admin can change it. */
export function usualGstRate(category: string | null | undefined): number | null {
  if (category === 'domestic') return 5;
  if (category === 'commercial') return 18;
  return null;
}

const startsAt = (entry: PriceListEntryResponse): number => Date.parse(entry.effective_from);

const sameChoice = (a: PriceListEntryResponse, b: PriceListEntryResponse): boolean =>
  a.customer_type === b.customer_type && a.branch_id === b.branch_id;

/** The price in force at `at` for each customer type and branch of one
 * cylinder type, the "all branches" one first. */
export function currentPrices(
  prices: readonly PriceListEntryResponse[],
  cylinderTypeId: string,
  at = new Date(),
): PriceListEntryResponse[] {
  const newestFirst = prices
    .filter((p) => p.cylinder_type_id === cylinderTypeId && startsAt(p) <= at.getTime())
    .sort((a, b) => startsAt(b) - startsAt(a));
  const current = newestFirst.filter(
    (entry, index) => newestFirst.findIndex((other) => sameChoice(other, entry)) === index,
  );
  const order = (p: PriceListEntryResponse): number =>
    (p.branch_id ? CUSTOMER_TYPES.length : 0) +
    CUSTOMER_TYPES.indexOf(p.customer_type as CustomerType);
  return current.sort((a, b) => order(a) - order(b));
}

/** Prices no longer in force, and ones that start later, newest first. */
export function otherPrices(
  prices: readonly PriceListEntryResponse[],
  cylinderTypeId: string,
  at = new Date(),
): PriceListEntryResponse[] {
  const current = new Set(currentPrices(prices, cylinderTypeId, at).map((p) => p.id));
  return prices
    .filter((p) => p.cylinder_type_id === cylinderTypeId && !current.has(p.id))
    .sort((a, b) => startsAt(b) - startsAt(a));
}

export interface PriceHeadline {
  /** The price to show in the list; `null` when none is in force. */
  readonly entry: PriceListEntryResponse | null;
  /** How many more prices are in force (other customers or branches). */
  readonly others: number;
}

/** One price for the list: the all-branches price for the cylinder's usual
 * customer, or else the first one in force. */
export function priceHeadline(
  prices: readonly PriceListEntryResponse[],
  cylinderTypeId: string,
  category: string | null | undefined,
  at = new Date(),
): PriceHeadline {
  const current = currentPrices(prices, cylinderTypeId, at);
  const usual = current.find(
    (p) => p.branch_id === null && p.customer_type === defaultCustomerType(category),
  );
  const entry = usual ?? current[0] ?? null;
  return { entry, others: entry ? current.length - 1 : 0 };
}

export function priceHeadlineText(headline: PriceHeadline): string {
  if (!headline.entry) return 'Not set';
  const amount = formatCurrencyInr(headline.entry.price);
  return headline.others > 0 ? `${amount} +${headline.others} more` : amount;
}

/** Says so when a cylinder charges other than the usual GST for its type. A
 * warning only: rates change by law, and the agency's accountant decides. */
export function gstRateWarning(category: string | null | undefined, rate: unknown): string | null {
  const usual = usualGstRate(category);
  if (usual === null || rate === null || rate === undefined || rate === '') return null;
  if (Number(rate) === usual) return null;
  return `GST on ${category} LPG is usually ${usual}%, not ${Number(rate)}%. Check with your accountant.`;
}

/** The agency's `prices_include_gst` setting, read as the server reads it. */
export function includesGstFrom(value: unknown): boolean {
  if (typeof value === 'string') {
    return ['true', 'yes', '1', 'inclusive'].includes(value.trim().toLowerCase());
  }
  return value === true || value === 1;
}

/** Says what the customer will pay, so a price is not typed with GST twice. */
export function priceHint(includesGst: boolean, gstRate: unknown, price: unknown): string {
  if (includesGst) return 'Includes GST. This is what the customer pays.';
  const amount = Number(price);
  const rate = gstRate === null || gstRate === undefined || gstRate === '' ? null : Number(gstRate);
  if (!(amount > 0) || rate === null) return 'Before GST. GST is added on the bill.';
  const withGst = Math.round(amount * (100 + rate)) / 100;
  return `Before GST. The customer pays ${formatCurrencyInr(withGst)} with GST.`;
}
