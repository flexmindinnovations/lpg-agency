import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../../../i18n/customer_strings.dart';
import 'invoice_presentation.dart';

/// Builds an A4 PDF of [invoice] on the device, so downloading needs no
/// extra backend call. The built-in PDF fonts have no rupee glyph, hence
/// "Rs." here instead of the on-screen symbol.
Future<Uint8List> buildInvoicePdf(
  InvoiceResponse invoice, {
  required Map<String, String> cylinderNames,
  required CustomerStrings s,
}) async {
  final money = NumberFormat.currency(
    locale: 'en_IN',
    symbol: 'Rs. ',
    decimalDigits: 2,
  );
  final dateFmt = DateFormat('dd MMM yyyy');
  final doc = pw.Document(title: invoice.reference);

  pw.Widget row(String l, String v, {bool bold = false}) => pw.Padding(
    padding: const pw.EdgeInsets.symmetric(vertical: 2),
    child: pw.Row(
      mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
      children: [
        pw.Text(
          l,
          style: pw.TextStyle(
            fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
          ),
        ),
        pw.Text(
          v,
          style: pw.TextStyle(
            fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
          ),
        ),
      ],
    ),
  );

  doc.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(36),
      build: (_) => [
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(
              'TAX INVOICE',
              style: pw.TextStyle(fontSize: 24, fontWeight: pw.FontWeight.bold),
            ),
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.end,
              children: [
                pw.Text(invoice.reference),
                pw.Text(
                  s.invoice.issued(
                    date: dateFmt.format(invoice.issuedAt.toLocal()),
                  ),
                ),
                pw.Text(s.invoice.status(status: invoice.statusLabel)),
              ],
            ),
          ],
        ),
        pw.SizedBox(height: 16),
        if (invoice.customerName != null) pw.Text(s.invoice.billedTo),
        if (invoice.customerName != null)
          pw.Text(
            invoice.customerName!,
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
          ),
        if (invoice.customerGstin != null)
          pw.Text(s.invoice.gstin(gstin: invoice.customerGstin!)),
        if (invoice.orderNumber != null)
          pw.Text(s.invoice.orderNumber(number: invoice.orderNumber!)),
        pw.SizedBox(height: 16),
        pw.TableHelper.fromTextArray(
          headers: [s.invoice.item, 'Qty', 'Rate', 'GST', 'Total'],
          data: [
            for (final l in invoice.lines)
              [
                cylinderNames[l.cylinderTypeId] ?? 'Cylinder',
                '${l.quantity}',
                money.format(l.unitPrice),
                money.format(l.taxAmount),
                money.format(l.totalAmount),
              ],
          ],
          headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold),
          headerDecoration: const pw.BoxDecoration(color: PdfColors.grey200),
          cellAlignments: {
            1: pw.Alignment.centerRight,
            2: pw.Alignment.centerRight,
            3: pw.Alignment.centerRight,
            4: pw.Alignment.centerRight,
          },
        ),
        pw.SizedBox(height: 12),
        pw.Align(
          alignment: pw.Alignment.centerRight,
          child: pw.SizedBox(
            width: 220,
            child: pw.Column(
              children: [
                row('Subtotal', money.format(invoice.subtotal)),
                row('GST', money.format(invoice.taxAmount)),
                pw.Divider(),
                row('Total', money.format(invoice.totalAmount), bold: true),
                row('Amount paid', money.format(invoice.amountPaid)),
                row(
                  'Balance due',
                  money.format(invoice.balanceDue),
                  bold: true,
                ),
              ],
            ),
          ),
        ),
        pw.SizedBox(height: 24),
        pw.Text(
          'This is a computer-generated invoice.',
          style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
        ),
      ],
    ),
  );
  return doc.save();
}

/// Opens the system share/save sheet with the invoice PDF.
Future<void> shareInvoicePdf(
  InvoiceResponse invoice, {
  required Map<String, String> cylinderNames,
  required CustomerStrings s,
}) async {
  final bytes = await buildInvoicePdf(
    invoice,
    cylinderNames: cylinderNames,
    s: s,
  );
  await Printing.sharePdf(bytes: bytes, filename: '${invoice.reference}.pdf');
}
