import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/widgets.dart';

/// Staff-facing names for the stock statuses, in the order a godown thinks
/// of them.
const stockStatusLabels = <String, String>{
  'filled': 'Filled',
  'empty': 'Empty',
  'damaged': 'Damaged',
  'leakage': 'Leaking',
  'quarantine': 'On hold',
  'repair': 'Under repair',
  'scrap': 'Scrap',
};

String stockStatusLabel(String status) =>
    stockStatusLabels[status] ?? LpgFormat.sentence(status);

/// What the OMC (oil company) sending a truck is called on the receipt.
const omcLabels = <String, String>{
  'iocl': 'Indane (IOCL)',
  'bpcl': 'Bharatgas (BPCL)',
  'hpcl': 'HP Gas (HPCL)',
  'other': 'Other',
};

/// A godown's holding of one cylinder type: the filled cylinders ready to
/// sell, and whatever else is on the floor (empties, damaged, on hold…).
class TypeStock {
  const TypeStock({required this.cylinderTypeId, required this.byStatus});

  final String cylinderTypeId;
  final Map<String, int> byStatus;

  int get filled => byStatus['filled'] ?? 0;

  /// Every status except filled that holds at least one cylinder, in the
  /// order of [stockStatusLabels].
  List<MapEntry<String, int>> get others => [
    for (final status in stockStatusLabels.keys)
      if (status != 'filled' && (byStatus[status] ?? 0) > 0)
        MapEntry(status, byStatus[status]!),
  ];
}

/// Folds balance lines into one [TypeStock] per cylinder type, keeping the
/// catalogue's order and dropping types the godown has never held.
List<TypeStock> groupByCylinderType(
  List<StockBalanceLine> lines,
  List<String> typeOrder,
) {
  final byType = <String, Map<String, int>>{};
  for (final line in lines) {
    final statuses = byType.putIfAbsent(line.cylinderTypeId, () => {});
    statuses[line.status] = (statuses[line.status] ?? 0) + line.quantity;
  }
  final known = {for (final id in typeOrder) id};
  return [
    for (final id in typeOrder)
      if (byType[id] case final statuses?
          when statuses.values.any((q) => q > 0))
        TypeStock(cylinderTypeId: id, byStatus: statuses),
    for (final entry in byType.entries)
      if (!known.contains(entry.key) && entry.value.values.any((q) => q > 0))
        TypeStock(cylinderTypeId: entry.key, byStatus: entry.value),
  ];
}

/// What happened at a godown, as the office would say it. The ledger names a
/// van transfer from the van's side: a godown "unloads" stock onto a van and
/// "loads" it when stock comes back.
String movementLabel(String type) => switch (type) {
  'grn_receipt' => 'Received from OMC',
  'omc_return' => 'Returned to OMC',
  'unload' => 'Sent out on a van',
  'load' => 'Came back from a van',
  'delivery' => 'Delivered',
  'collection' => 'Empties collected',
  'status_change' => 'Moved between statuses',
  'adjustment' => 'Corrected by hand',
  'reconciliation' => 'Count booked',
  'reservation' => 'Held for an order',
  'reservation_release' => 'Hold released',
  _ => LpgFormat.sentence(type),
};

IconData movementIcon(String type) => switch (type) {
  'grn_receipt' => LpgIcons.download,
  'omc_return' => LpgIcons.upload,
  'load' || 'unload' => LpgIcons.van,
  'delivery' || 'collection' => LpgIcons.package,
  'reconciliation' => LpgIcons.check,
  _ => LpgIcons.history,
};

/// `1` when a movement added to the godown's stock, `-1` when it took away,
/// `null` when it only moved cylinders between statuses.
int? movementDirection(InventoryTransaction t) => switch (t.type) {
  'grn_receipt' || 'load' || 'collection' || 'reservation_release' => 1,
  'unload' || 'delivery' || 'omc_return' || 'reservation' => -1,
  'reconciliation' => t.fromStatus == null ? 1 : -1,
  _ => null,
};

/// `+40` for a receipt, `-3` for a delivery, `5` for a status move.
String signedQuantity(InventoryTransaction t) => switch (movementDirection(t)) {
  1 => '+${t.quantity}',
  -1 => '-${t.quantity}',
  _ => '${t.quantity}',
};

/// "Filled" for a movement into one status, "Filled to Leaking" for a move
/// between two.
String movementStatus(InventoryTransaction t) {
  final to = stockStatusLabel(t.toStatus);
  final from = t.fromStatus;
  if (from == null || from == t.toStatus) return to;
  return '${stockStatusLabel(from)} to $to';
}
