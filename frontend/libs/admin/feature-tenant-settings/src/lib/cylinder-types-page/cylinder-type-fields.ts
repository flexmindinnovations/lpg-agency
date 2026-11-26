import type { CylinderSizeResponse, CylinderTypeResponse } from '@lpg/shared/data-access';

/** HSN for liquefied petroleum gas — every cylinder type an agency sells. */
export const LPG_HSN_CODE = '27111900';
export const HSN_PATTERN = /^(?:[0-9]{4}|[0-9]{6}|[0-9]{8})$/;
export const GST_RATE_HINT = 'LPG: 5% for domestic, 18% for commercial cylinders.';
export const HSN_MESSAGES = {
  required: 'HSN code is required.',
  pattern: 'HSN is 4, 6 or 8 digits.',
};
export const GST_RATE_MESSAGES = {
  required: 'GST rate is required.',
  min: 'Rate cannot be negative.',
  max: 'The highest GST rate is 28%.',
};

const CATEGORY_LABELS: Record<string, string> = {
  domestic: 'Domestic',
  commercial: 'Commercial and industrial',
};

export function categoryLabel(category: string | null | undefined): string {
  return (category && CATEGORY_LABELS[category]) || '—';
}

export interface CylinderCategoryOption {
  readonly value: string;
  readonly label: string;
}

/** The "Cylinder type" choices that have at least one size to offer. */
export function categoryOptions(sizes: readonly CylinderSizeResponse[]): CylinderCategoryOption[] {
  return Object.entries(CATEGORY_LABELS)
    .filter(([category]) => sizes.some((size) => size.category === category))
    .map(([value, label]) => ({ value, label }));
}

export function sizesIn(
  sizes: readonly CylinderSizeResponse[],
  category: string | null,
): CylinderSizeResponse[] {
  return sizes.filter((size) => size.category === category);
}

/** Sizes no other record already holds — an agency adds each size once. */
export function sizesNotTaken(
  sizes: readonly CylinderSizeResponse[],
  others: readonly CylinderTypeResponse[],
): CylinderSizeResponse[] {
  const names = new Set(others.map((other) => other.name.toLowerCase()));
  return sizes.filter((size) => !names.has(size.name.toLowerCase()));
}

/** "19 kg", from the API's "19.00". */
export function weightLabel(weightKg: string): string {
  return `${Number(weightKg)} kg`;
}

/** "orders, prices and invoices" */
export function joinWithAnd(items: readonly string[]): string {
  if (items.length < 2) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}
