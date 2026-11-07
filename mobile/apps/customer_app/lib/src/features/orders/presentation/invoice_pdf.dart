import 'dart:io';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:open_filex/open_filex.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../../../i18n/customer_strings.dart';
import 'invoice_presentation.dart';

const _fontDir = 'packages/design_system/fonts/inter';

PdfColor _pdf(Color c) => PdfColor.fromInt(c.toARGB32());

/// Loads the bundled Inter faces (they carry the rupee glyph). Returns null
/// when the assets cannot be read, and the PDF falls back to its built-in
/// fonts with "Rs." instead of the symbol.
Future<pw.ThemeData?> _loadTheme() async {
  try {
    Future<pw.Font> f(String n) async =>
        pw.Font.ttf(await rootBundle.load('$_fontDir/$n.ttf'));
    return pw.ThemeData.withFont(
      base: await f('Inter-Regular'),
      bold: await f('Inter-Bold'),
    );
  } catch (_) {
    return null;
  }
}

/// Builds an A4 PDF of [invoice] on the device, laid out like the on-screen
/// invoice: always on the light palette (it is a printout), with the same
/// status chip, ruled item table, totals panel and payments list.
Future<Uint8List> buildInvoicePdf(
  InvoiceResponse invoice, {
  required Map<String, String> cylinderNames,
  required CustomerStrings s,
}) async {
  final theme = await _loadTheme();
  final money = NumberFormat.currency(
    locale: 'en_IN',
    symbol: theme == null ? 'Rs. ' : '₹',
    decimalDigits: 2,
  );
  final dateFmt = DateFormat('dd MMM yyyy');
  final c = LpgTheme.light.extension<LpgColors>()!;
  final ink = _pdf(c.textPrimary);
  final muted = _pdf(c.textSecondary);
  final rule = _pdf(c.rowDivider);
  final panel = _pdf(c.surfaceOverlay);
  final brand = _pdf(c.actionPrimary);
  final tone = invoice.statusSeverity.tone;
  final chipFg = _pdf(tone.foreground(c));
  final chipBg = _pdf(tone.container(c));
  final balanceDue = invoice.balanceDue;

  final doc = pw.Document(title: invoice.reference, theme: theme);

  pw.TextStyle ts({
    double size = 10,
    bool bold = false,
    PdfColor? color,
    double? spacing,
  }) => pw.TextStyle(
    fontSize: size,
    fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
    color: color ?? ink,
    letterSpacing: spacing,
  );

  pw.Widget kv(String l, String v, {bool bold = false, PdfColor? color}) =>
      pw.Padding(
        padding: const pw.EdgeInsets.symmetric(vertical: 3),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(l, style: ts(bold: bold)),
            pw.Text(
              v,
              style: ts(bold: bold, color: color),
            ),
          ],
        ),
      );

  pw.Widget cell(
    String t, {
    bool right = false,
    bool bold = false,
    PdfColor? color,
    double size = 10,
  }) => pw.Padding(
    padding: const pw.EdgeInsets.symmetric(horizontal: 8, vertical: 7),
    child: pw.Text(
      t,
      textAlign: right ? pw.TextAlign.right : pw.TextAlign.left,
      style: ts(bold: bold, color: color, size: size),
    ),
  );

  final chip = pw.Container(
    padding: const pw.EdgeInsets.symmetric(horizontal: 9, vertical: 4),
    decoration: pw.BoxDecoration(
      color: chipBg,
      borderRadius: pw.BorderRadius.circular(20),
    ),
    child: pw.Row(
      mainAxisSize: pw.MainAxisSize.min,
      children: [
        pw.Container(
          width: 6,
          height: 6,
          decoration: pw.BoxDecoration(
            color: chipFg,
            shape: pw.BoxShape.circle,
          ),
        ),
        pw.SizedBox(width: 5),
        pw.Text(
          invoice.statusLabel,
          style: ts(size: 9, bold: true, spacing: 0.4),
        ),
      ],
    ),
  );

  doc.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(36),
      build: (_) => [
        pw.Container(height: 4, color: brand),
        pw.SizedBox(height: 16),
        pw.Row(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text('INVOICE', style: ts(size: 24, bold: true, spacing: 1)),
                pw.SizedBox(height: 2),
                pw.Text(invoice.reference, style: ts(color: muted)),
              ],
            ),
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.end,
              children: [
                pw.Text(
                  s.invoice.issued(
                    date: dateFmt.format(invoice.issuedAt.toLocal()),
                  ),
                  style: ts(color: muted),
                ),
                pw.SizedBox(height: 6),
                chip,
              ],
            ),
          ],
        ),
        pw.SizedBox(height: 20),
        if (invoice.customerName != null || invoice.orderNumber != null)
          pw.Row(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              if (invoice.customerName != null)
                pw.Column(
                  crossAxisAlignment: pw.CrossAxisAlignment.start,
                  children: [
                    pw.Text(s.invoice.billedTo, style: ts(color: muted)),
                    pw.Text(invoice.customerName!, style: ts(bold: true)),
                    if (invoice.customerGstin != null)
                      pw.Text(
                        s.invoice.gstin(gstin: invoice.customerGstin!),
                        style: ts(color: muted, size: 9),
                      ),
                  ],
                )
              else
                pw.SizedBox(),
              if (invoice.orderNumber != null)
                pw.Column(
                  crossAxisAlignment: pw.CrossAxisAlignment.end,
                  children: [
                    pw.Text(s.invoice.order, style: ts(color: muted)),
                    pw.Text(invoice.orderNumber!, style: ts(bold: true)),
                  ],
                ),
            ],
          ),
        pw.SizedBox(height: 20),
        pw.Table(
          border: pw.TableBorder(
            horizontalInside: pw.BorderSide(color: rule, width: 0.6),
            bottom: pw.BorderSide(color: rule, width: 0.6),
          ),
          columnWidths: {
            0: const pw.FlexColumnWidth(3),
            1: const pw.FlexColumnWidth(0.8),
            2: const pw.FlexColumnWidth(1.5),
            3: const pw.FlexColumnWidth(1.4),
            4: const pw.FlexColumnWidth(1.6),
          },
          children: [
            pw.TableRow(
              decoration: pw.BoxDecoration(
                color: panel,
                borderRadius: const pw.BorderRadius.vertical(
                  top: pw.Radius.circular(4),
                ),
              ),
              children: [
                cell(s.invoice.item, bold: true, color: muted, size: 9),
                cell('Qty', right: true, bold: true, color: muted, size: 9),
                cell('Rate', right: true, bold: true, color: muted, size: 9),
                cell('GST', right: true, bold: true, color: muted, size: 9),
                cell('Total', right: true, bold: true, color: muted, size: 9),
              ],
            ),
            for (final l in invoice.lines)
              pw.TableRow(
                children: [
                  cell(
                    cylinderNames[l.cylinderTypeId] ?? 'Cylinder',
                    bold: true,
                  ),
                  cell('${l.quantity}', right: true),
                  cell(money.format(l.unitPrice), right: true),
                  cell(money.format(l.taxAmount), right: true, color: muted),
                  cell(money.format(l.totalAmount), right: true, bold: true),
                ],
              ),
          ],
        ),
        pw.SizedBox(height: 14),
        pw.Align(
          alignment: pw.Alignment.centerRight,
          child: pw.Container(
            width: 240,
            padding: const pw.EdgeInsets.all(12),
            decoration: pw.BoxDecoration(
              color: panel,
              borderRadius: pw.BorderRadius.circular(6),
            ),
            child: pw.Column(
              children: [
                kv('Subtotal', money.format(invoice.subtotal)),
                kv('GST', money.format(invoice.taxAmount)),
                pw.Divider(color: rule, thickness: 0.6),
                kv('Total', money.format(invoice.totalAmount), bold: true),
                kv(
                  'Amount paid',
                  money.format(invoice.amountPaid),
                  color: _pdf(c.statusSuccess),
                ),
                kv(
                  'Balance due',
                  money.format(balanceDue),
                  bold: true,
                  color: balanceDue > 0 ? _pdf(c.statusDanger) : null,
                ),
              ],
            ),
          ),
        ),
        if (invoice.payments.isNotEmpty) ...[
          pw.SizedBox(height: 20),
          pw.Text(s.invoice.payments, style: ts(color: muted)),
          pw.SizedBox(height: 4),
          pw.Divider(color: rule, thickness: 0.6),
          for (final p in invoice.payments)
            kv(
              '${LpgFormat.statusLabel(p.method)}  ·  '
              '${LpgFormat.shortDate(p.collectedAt)}',
              money.format(p.amount),
            ),
        ],
        pw.SizedBox(height: 28),
        pw.Text(
          'This is a computer-generated invoice.',
          style: ts(size: 9, color: muted),
        ),
      ],
    ),
  );
  return doc.save();
}

/// Where a downloaded invoice ended up.
class SavedInvoice {
  const SavedInvoice({required this.fileName, required this.openPath});

  /// The file name in Downloads.
  final String fileName;

  /// A real file path an installed PDF viewer can be pointed at.
  final String openPath;
}

/// Saves the invoice PDF in the device's Downloads folder (MediaStore on
/// Android 10+, so no storage permission is asked for). Returns null on
/// platforms with no shared Downloads folder, where the system save sheet is
/// shown instead.
Future<SavedInvoice?> downloadInvoicePdf(
  InvoiceResponse invoice, {
  required Map<String, String> cylinderNames,
  required CustomerStrings s,
}) async {
  final bytes = await buildInvoicePdf(
    invoice,
    cylinderNames: cylinderNames,
    s: s,
  );
  final fileName = '${invoice.reference}.pdf';
  if (kIsWeb || !Platform.isAndroid) {
    await Printing.sharePdf(bytes: bytes, filename: fileName);
    return null;
  }
  await FileSaver.instance.saveToDownloads(
    name: invoice.reference,
    bytes: bytes,
    fileExtension: 'pdf',
    mimeType: MimeType.pdf,
  );
  // MediaStore hands back a content:// URI, which PDF viewers can't always
  // read; a cache copy opens reliably through the app's file provider.
  final cache = File('${Directory.systemTemp.path}/$fileName');
  await cache.writeAsBytes(bytes, flush: true);
  return SavedInvoice(fileName: fileName, openPath: cache.path);
}

/// Opens a saved invoice in the device's PDF viewer. False when none exists.
Future<bool> openInvoicePdf(SavedInvoice saved) async {
  final result = await OpenFilex.open(saved.openPath, type: 'application/pdf');
  return result.type == ResultType.done;
}

/// Opens the system share sheet with the invoice PDF.
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
