import { invoiceFileName } from './invoice-file-name';

describe('invoiceFileName', () => {
  const at = new Date(2026, 10, 7, 9, 5, 3);

  it('carries the invoice number and the local date and time', () => {
    expect(invoiceFileName('INV-2026-000001', at)).toBe('INV-2026-000001_2026-11-07_09-05-03.pdf');
  });

  it('keeps characters a file name cannot hold out of the name', () => {
    expect(invoiceFileName('INV/26:1', at)).toBe('INV-26-1_2026-11-07_09-05-03.pdf');
  });

  it('still names an invoice that has no number', () => {
    expect(invoiceFileName(null, at)).toBe('invoice_2026-11-07_09-05-03.pdf');
  });
});
