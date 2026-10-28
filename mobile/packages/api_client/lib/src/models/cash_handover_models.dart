import 'decimal_json.dart';

/// Note values a handover can be counted in, largest first (ADR-066).
const List<int> cashDenominations = [500, 200, 100, 50, 20, 10, 5, 2, 1];

/// `{"500": 2}` as sent by the backend -> `{500: 2}`; null when absent.
Map<int, int>? parseDenominations(dynamic raw) {
  if (raw is! Map || raw.isEmpty) return null;
  return {
    for (final entry in raw.entries)
      int.parse(entry.key.toString()): (entry.value as num).toInt(),
  };
}

/// The JSON body shape for [denominations]: string keys, zero counts left out.
Map<String, int> denominationsToJson(Map<int, int> denominations) => {
  for (final entry in denominations.entries)
    if (entry.value > 0) entry.key.toString(): entry.value,
};

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
    this.denominations,
    this.varianceReason,
    this.upiExpected,
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
    denominations: parseDenominations(json['denominations']),
    varianceReason: json['variance_reason'] as String?,
    upiExpected: asDoubleOrNull(json['upi_expected']),
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

  /// Notes and coins the driver counted, note value -> count. Null for a
  /// handover declared as a bare amount.
  final Map<int, int>? denominations;

  /// Why the cash differed from the deliveries, when it did.
  final String? varianceReason;

  /// UPI collected at the doorstep on the same route (informational).
  final double? upiExpected;

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
    this.upiAmount = 0,
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
        upiAmount: asDoubleOrNull(json['upi_amount']) ?? 0,
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

  /// UPI collected at the doorstep on this route — not part of the cash to
  /// hand over, shown beside it.
  final double upiAmount;
  final CashHandover? handover;

  /// The driver has already declared this route's cash.
  bool get isDeclared => handover != null;

  /// The route is finished and the cash still needs declaring — the state
  /// that surfaces the "reconcile your cash" prompt.
  bool get isPending => routeStatus == 'completed' && handover == null;
}

class CashHandoverReviewResponse {
  final String id;
  final String outcome;
  final String? note;
  final String reviewedBy;
  final DateTime reviewedAt;

  CashHandoverReviewResponse({
    required this.id,
    required this.outcome,
    this.note,
    required this.reviewedBy,
    required this.reviewedAt,
  });

  factory CashHandoverReviewResponse.fromJson(Map<String, dynamic> json) =>
      CashHandoverReviewResponse(
        id: json['id'] as String? ?? '',
        outcome: json['outcome'] as String? ?? '',
        note: json['note'] as String?,
        reviewedBy: json['reviewed_by'] as String? ?? '',
        reviewedAt: json['reviewed_at'] != null
            ? DateTime.parse(json['reviewed_at'] as String)
            : DateTime.now(),
      );
}

class CashHandoverRegisterEntryResponse {
  final String id;
  final String? handoverNumber;
  final String driverId;
  final String driverName;
  final String routeId;
  final DateTime routeDate;
  final String? vehicleRegistration;
  final int cashStopCount;
  final double expectedAmount;
  final double actualAmount;
  final double shortfall;
  final double excess;
  final DateTime declaredAt;
  final String reviewStatus;
  final CashHandoverReviewResponse? review;
  final Map<int, int>? denominations;
  final String? varianceReason;
  final double? upiExpected;

  CashHandoverRegisterEntryResponse({
    required this.id,
    this.handoverNumber,
    required this.driverId,
    required this.driverName,
    required this.routeId,
    required this.routeDate,
    this.vehicleRegistration,
    required this.cashStopCount,
    required this.expectedAmount,
    required this.actualAmount,
    required this.shortfall,
    required this.excess,
    required this.declaredAt,
    required this.reviewStatus,
    this.review,
    this.denominations,
    this.varianceReason,
    this.upiExpected,
  });

  factory CashHandoverRegisterEntryResponse.fromJson(
    Map<String, dynamic> json,
  ) => CashHandoverRegisterEntryResponse(
    id: json['id'] as String? ?? '',
    handoverNumber: json['handover_number'] as String?,
    driverId: json['driver_id'] as String? ?? '',
    driverName: json['driver_name'] as String? ?? '',
    routeId: json['route_id'] as String? ?? '',
    routeDate: json['route_date'] != null
        ? DateTime.parse(json['route_date'] as String)
        : DateTime.now(),
    vehicleRegistration: json['vehicle_registration'] as String?,
    cashStopCount: json['cash_stop_count'] as int? ?? 0,
    expectedAmount: asDouble(json['expected_amount']),
    actualAmount: asDouble(json['actual_amount']),
    shortfall: asDouble(json['shortfall']),
    excess: asDouble(json['excess']),
    declaredAt: json['declared_at'] != null
        ? DateTime.parse(json['declared_at'] as String)
        : DateTime.now(),
    reviewStatus: json['review_status'] as String? ?? 'pending',
    denominations: parseDenominations(json['denominations']),
    varianceReason: json['variance_reason'] as String?,
    upiExpected: asDoubleOrNull(json['upi_expected']),
    review: json['review'] != null
        ? CashHandoverReviewResponse.fromJson(
            json['review'] as Map<String, dynamic>,
          )
        : null,
  );
}

/// Cash one driver is carrying: collected on routes with no handover yet.
class DriverCashInHand {
  const DriverCashInHand({
    required this.driverId,
    required this.driverName,
    required this.routeCount,
    required this.stopCount,
    required this.cashAmount,
    required this.upiAmount,
    required this.oldestRouteDate,
  });

  factory DriverCashInHand.fromJson(Map<String, dynamic> json) =>
      DriverCashInHand(
        driverId: json['driver_id'] as String,
        driverName: json['driver_name'] as String,
        routeCount: json['route_count'] as int,
        stopCount: json['stop_count'] as int,
        cashAmount: asDouble(json['cash_amount']),
        upiAmount: asDouble(json['upi_amount']),
        oldestRouteDate: DateTime.parse(json['oldest_route_date'] as String),
      );

  final String driverId;
  final String driverName;
  final int routeCount;
  final int stopCount;
  final double cashAmount;
  final double upiAmount;
  final DateTime oldestRouteDate;
}

/// `GET /cash-handovers/cash-in-hand` (and `/mine` for a driver).
class CashInHand {
  const CashInHand({required this.totalCash, required this.drivers});

  factory CashInHand.fromJson(Map<String, dynamic> json) => CashInHand(
    totalCash: asDouble(json['total_cash']),
    drivers: [
      for (final d in json['drivers'] as List<dynamic>? ?? const [])
        DriverCashInHand.fromJson(d as Map<String, dynamic>),
    ],
  );

  final double totalCash;
  final List<DriverCashInHand> drivers;
}

class CashBookCollection {
  const CashBookCollection({
    required this.method,
    required this.paymentCount,
    required this.amount,
  });

  factory CashBookCollection.fromJson(Map<String, dynamic> json) =>
      CashBookCollection(
        method: json['method'] as String,
        paymentCount: json['payment_count'] as int,
        amount: asDouble(json['amount']),
      );

  final String method;
  final int paymentCount;
  final double amount;
}

/// One IST day of the cash book (`GET /cash-handovers/cash-book`).
class CashBook {
  const CashBook({
    required this.date,
    required this.collections,
    required this.totalCollected,
    required this.handoverCount,
    required this.expectedTotal,
    required this.handedOverTotal,
    required this.shortfallTotal,
    required this.excessTotal,
    required this.acceptedTotal,
    required this.disputedTotal,
    required this.pendingTotal,
    required this.pendingCount,
    required this.cashInHandTotal,
  });

  factory CashBook.fromJson(Map<String, dynamic> json) => CashBook(
    date: json['date'] as String,
    collections: [
      for (final c in json['collections'] as List<dynamic>? ?? const [])
        CashBookCollection.fromJson(c as Map<String, dynamic>),
    ],
    totalCollected: asDouble(json['total_collected']),
    handoverCount: json['handover_count'] as int,
    expectedTotal: asDouble(json['expected_total']),
    handedOverTotal: asDouble(json['handed_over_total']),
    shortfallTotal: asDouble(json['shortfall_total']),
    excessTotal: asDouble(json['excess_total']),
    acceptedTotal: asDouble(json['accepted_total']),
    disputedTotal: asDouble(json['disputed_total']),
    pendingTotal: asDouble(json['pending_total']),
    pendingCount: json['pending_count'] as int,
    cashInHandTotal: asDouble(json['cash_in_hand_total']),
  );

  /// `YYYY-MM-DD` (IST).
  final String date;
  final List<CashBookCollection> collections;
  final double totalCollected;
  final int handoverCount;
  final double expectedTotal;
  final double handedOverTotal;
  final double shortfallTotal;
  final double excessTotal;
  final double acceptedTotal;
  final double disputedTotal;
  final double pendingTotal;
  final int pendingCount;
  final double cashInHandTotal;
}
