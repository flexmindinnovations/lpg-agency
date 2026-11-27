/** `INV-2026-000001_2026-11-27_14-30-05.pdf`: the invoice number, then the
 * local date and time. No colons, which Windows does not allow in a name. */
export function invoiceFileName(invoiceNumber: string | null | undefined, at = new Date()): string {
  const two = (value: number): string => String(value).padStart(2, '0');
  const date = `${at.getFullYear()}-${two(at.getMonth() + 1)}-${two(at.getDate())}`;
  const time = `${two(at.getHours())}-${two(at.getMinutes())}-${two(at.getSeconds())}`;
  const stem = (invoiceNumber ?? 'invoice').replace(/[^A-Za-z0-9._-]+/g, '-');
  return `${stem}_${date}_${time}.pdf`;
}
