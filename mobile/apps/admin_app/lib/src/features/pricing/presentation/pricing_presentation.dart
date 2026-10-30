import 'package:api_client/api_client.dart';

/// The kinds of customer a price can be set for, in the order the office
/// thinks of them.
const customerTypeLabels = <String, String>{
  'domestic': 'Domestic',
  'commercial': 'Commercial',
  'industrial': 'Industrial',
  'government': 'Government',
};

String customerTypeLabel(String type) =>
    customerTypeLabels[type] ??
    '${type.substring(0, 1).toUpperCase()}${type.substring(1)}';

/// Prices more than this far from the old one ask for a second look before
/// saving, so a slipped decimal point cannot go out unnoticed.
const largeChangeRatio = 0.25;

/// A price can never be set to more than this; far above any cylinder.
const maxPrice = 100000.0;

/// Whether moving from [oldPrice] to [newPrice] is big enough to double-check.
bool isLargeChange(double oldPrice, double newPrice) =>
    oldPrice > 0 && (newPrice - oldPrice).abs() / oldPrice > largeChangeRatio;

/// "+12%" or "-8%"; whole percent.
String changeLabel(double oldPrice, double newPrice) {
  final pct = ((newPrice - oldPrice) / oldPrice * 100).round();
  return '${pct > 0 ? '+' : ''}$pct%';
}

/// All the prices ever set for one cylinder type, customer type and branch,
/// newest first. The one in force is the latest whose date has passed;
/// later ones are scheduled changes.
class PriceRow {
  const PriceRow({
    required this.cylinderTypeId,
    required this.customerType,
    required this.branchId,
    required this.entries,
  });

  final String cylinderTypeId;
  final String customerType;

  /// `null` for the agency-wide price.
  final String? branchId;

  /// Newest first.
  final List<PriceEntry> entries;

  /// The price in force at [now], or `null` while every price is still
  /// scheduled for later.
  PriceEntry? current([DateTime? now]) {
    final at = now ?? DateTime.now();
    for (final e in entries) {
      if (_started(e, at)) return e;
    }
    return null;
  }

  /// A price set "now" is stamped by the server, and a phone's clock can run
  /// seconds or minutes behind it. Without some slack a price saved a moment
  /// ago would look like a change scheduled for later.
  static const clockSkew = Duration(minutes: 2);

  static bool _started(PriceEntry e, DateTime at) =>
      !e.effectiveFrom.isAfter(at.add(clockSkew));

  /// Changes that have not started yet, soonest first.
  List<PriceEntry> upcoming([DateTime? now]) {
    final at = now ?? DateTime.now();
    return [
      for (final e in entries.reversed)
        if (!_started(e, at)) e,
    ];
  }

  /// Prices that were replaced, newest first.
  List<PriceEntry> earlier([DateTime? now]) {
    final cur = current(now);
    if (cur == null) return const [];
    final i = entries.indexOf(cur);
    return entries.sublist(i + 1);
  }
}

/// Folds the price history into one [PriceRow] per cylinder type, customer
/// type and branch, ordered by the catalogue, then customer type, with the
/// agency-wide price before branch prices.
List<PriceRow> buildPriceRows(
  Iterable<PriceEntry> entries,
  List<String> typeOrder,
) {
  final groups = <(String, String, String?), List<PriceEntry>>{};
  for (final e in entries) {
    groups
        .putIfAbsent((e.cylinderTypeId, e.customerType, e.branchId), () => [])
        .add(e);
  }
  final customerOrder = customerTypeLabels.keys.toList();
  int typeIndex(String id) {
    final i = typeOrder.indexOf(id);
    return i < 0 ? typeOrder.length : i;
  }

  int customerIndex(String type) {
    final i = customerOrder.indexOf(type);
    return i < 0 ? customerOrder.length : i;
  }

  final rows = [
    for (final g in groups.entries)
      PriceRow(
        cylinderTypeId: g.key.$1,
        customerType: g.key.$2,
        branchId: g.key.$3,
        entries: [...g.value]
          ..sort((a, b) => b.effectiveFrom.compareTo(a.effectiveFrom)),
      ),
  ];
  rows.sort((a, b) {
    final byType = typeIndex(
      a.cylinderTypeId,
    ).compareTo(typeIndex(b.cylinderTypeId));
    if (byType != 0) return byType;
    final byCustomer = customerIndex(
      a.customerType,
    ).compareTo(customerIndex(b.customerType));
    if (byCustomer != 0) return byCustomer;
    return (a.branchId ?? '').compareTo(b.branchId ?? '');
  });
  return rows;
}
