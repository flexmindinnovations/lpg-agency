import 'decimal_json.dart';

/// One declared end-of-route cash handover — mirrors the backend's
/// `CashHandoverResponse`. Immutable once declared; `shortfall` is computed
/// server-side (`expected - actual`, floored at zero).
class CashHandover {
  const CashHandover({
    required this.id,
    required this.driverId,
    required this.routeId,
    required this.expectedAmount,
    required this.actualAmount,
    required this.shortfall,
    required this.declaredBy,
    required this.declaredAt,
    this.handoverNumber,
  });

  factory CashHandover.fromJson(Map<String, dynamic> json) => CashHandover(
    id: json['id'] as String,
    handoverNumber: json['handover_number'] as String?,
    driverId: json['driver_id'] as String,
    routeId: json['route_id'] as String,
    expectedAmount: asDouble(json['expected_amount']),
    actualAmount: asDouble(json['actual_amount']),
    shortfall: asDouble(json['shortfall']),
    declaredBy: json['declared_by'] as String,
    declaredAt: DateTime.parse(json['declared_at'] as String),
  );

  final String id;
  final String? handoverNumber;
  final String driverId;
  final String routeId;
  final double expectedAmount;
  final double actualAmount;
  final double shortfall;
  final String declaredBy;
  final DateTime declaredAt;

  /// Amount handed over beyond what was expected (0 when short or exact) —
  /// the receipt shows this as "Over by ₹X".
  double get surplus {
    final over = actualAmount - expectedAmount;
    return over > 0 ? over : 0;
  }
}

/// What the Driver App's cash-handover screen reads for a route — mirrors
/// the backend's `RouteCashHandoverResponse` (`GET /cash-handovers/for-route
/// /{route_id}`). `handover` is null until the driver has declared.
class RouteCashHandover {
  const RouteCashHandover({
    required this.routeId,
    required this.driverId,
    required this.routeStatus,
    required this.routeDate,
    required this.expectedAmount,
    required this.cashStopCount,
    this.handover,
  });

  factory RouteCashHandover.fromJson(Map<String, dynamic> json) =>
      RouteCashHandover(
        routeId: json['route_id'] as String,
        driverId: json['driver_id'] as String,
        routeStatus: json['route_status'] as String,
        routeDate: DateTime.parse(json['route_date'] as String),
        expectedAmount: asDouble(json['expected_amount']),
        cashStopCount: json['cash_stop_count'] as int,
        handover: json['handover'] == null
            ? null
            : CashHandover.fromJson(json['handover'] as Map<String, dynamic>),
      );

  final String routeId;
  final String driverId;
  final String routeStatus;
  final DateTime routeDate;
  final double expectedAmount;
  final int cashStopCount;
  final CashHandover? handover;

  /// The driver has already declared this route's cash.
  bool get isDeclared => handover != null;

  /// The route is finished and the cash still needs declaring — the state
  /// that surfaces the "reconcile your cash" prompt.
  bool get isPending => routeStatus == 'completed' && handover == null;
}
