import 'package:intl/intl.dart';

/// Display formatting shared by every screen, so an amount or a date reads
/// the same in the order list, the invoice and the driver's cash summary.
abstract final class LpgFormat {
  static final _currency = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 2,
  );
  static final _currencyWhole = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 0,
  );

  /// `₹1,24,000.50` — Indian digit grouping, always two decimals.
  static String currency(num amount) => _currency.format(amount);

  /// `₹1,24,001` — for headline figures where paise are noise.
  static String currencyWhole(num amount) => _currencyWhole.format(amount);

  /// `12 Oct 2026`
  static String date(DateTime value) =>
      DateFormat('d MMM yyyy').format(value.toLocal());

  /// `12 Oct`
  static String shortDate(DateTime value) =>
      DateFormat('d MMM').format(value.toLocal());

  /// `12 Oct 2026, 4:05 PM`
  static String dateTime(DateTime value) =>
      DateFormat('d MMM yyyy, h:mm a').format(value.toLocal());

  /// `4:05 PM`
  static String time(DateTime value) =>
      DateFormat('h:mm a').format(value.toLocal());

  /// "just now", "5 min ago", "3 h ago", "yesterday", then a short date.
  static String relative(DateTime value, {DateTime? now}) {
    final reference = now ?? DateTime.now();
    final diff = reference.difference(value);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
    if (diff.inHours < 24) return '${diff.inHours} h ago';
    if (diff.inDays == 1) return 'yesterday';
    if (diff.inDays < 7) return '${diff.inDays} days ago';
    return shortDate(value);
  }

  /// A backend status code as a badge label: `out_for_delivery` ->
  /// `OUT FOR DELIVERY`.
  static String statusLabel(String status) =>
      status.replaceAll('_', ' ').toUpperCase();

  /// A backend code as running text: `out_for_delivery` -> `Out for
  /// delivery`.
  static String sentence(String code) {
    final words = code.replaceAll('_', ' ').trim();
    if (words.isEmpty) return words;
    return words[0].toUpperCase() + words.substring(1).toLowerCase();
  }
}
