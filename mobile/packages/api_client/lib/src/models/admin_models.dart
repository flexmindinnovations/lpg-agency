class DashboardSummaryResponse {
  final int customerCount;
  final int driverCount;
  final int vehicleCount;
  final Map<String, int> vehiclesByStatus;
  final int warehouseCount;
  final int cylinderTypeCount;
  final Map<String, dynamic> inventoryByStatus;
  final List<CylinderTypePriceCardResponse> priceCards;
  final List<DashboardActivityEntryResponse> recentActivity;

  DashboardSummaryResponse({
    required this.customerCount,
    required this.driverCount,
    required this.vehicleCount,
    required this.vehiclesByStatus,
    required this.warehouseCount,
    required this.cylinderTypeCount,
    required this.inventoryByStatus,
    required this.priceCards,
    required this.recentActivity,
  });

  factory DashboardSummaryResponse.fromJson(Map<String, dynamic> json) {
    return DashboardSummaryResponse(
      customerCount: json['customer_count'] as int? ?? 0,
      driverCount: json['driver_count'] as int? ?? 0,
      vehicleCount: json['vehicle_count'] as int? ?? 0,
      vehiclesByStatus: Map<String, int>.from(json['vehicles_by_status'] ?? {}),
      warehouseCount: json['warehouse_count'] as int? ?? 0,
      cylinderTypeCount: json['cylinder_type_count'] as int? ?? 0,
      inventoryByStatus: Map<String, dynamic>.from(json['inventory_by_status'] ?? {}),
      priceCards: (json['price_cards'] as List<dynamic>? ?? [])
          .map((e) => CylinderTypePriceCardResponse.fromJson(e as Map<String, dynamic>))
          .toList(),
      recentActivity: (json['recent_activity'] as List<dynamic>? ?? [])
          .map((e) => DashboardActivityEntryResponse.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class CylinderTypePriceCardResponse {
  final String cylinderTypeId;
  final String name;
  final double weightKg;
  final String customerType;
  final double price;

  CylinderTypePriceCardResponse({
    required this.cylinderTypeId,
    required this.name,
    required this.weightKg,
    required this.customerType,
    required this.price,
  });

  factory CylinderTypePriceCardResponse.fromJson(Map<String, dynamic> json) {
    return CylinderTypePriceCardResponse(
      cylinderTypeId: json['cylinder_type_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      weightKg: (json['weight_kg'] as num?)?.toDouble() ?? 0.0,
      customerType: json['customer_type'] as String? ?? '',
      price: double.tryParse(json['price']?.toString() ?? '0') ?? 0.0,
    );
  }
}

class DashboardActivityEntryResponse {
  final String id;
  final String actorDisplayName;
  final String entityName;
  final String entityId;
  final String entityDisplayName;
  final String action;
  final DateTime performedAt;

  DashboardActivityEntryResponse({
    required this.id,
    required this.actorDisplayName,
    required this.entityName,
    required this.entityId,
    required this.entityDisplayName,
    required this.action,
    required this.performedAt,
  });

  factory DashboardActivityEntryResponse.fromJson(Map<String, dynamic> json) {
    return DashboardActivityEntryResponse(
      id: json['id'] as String? ?? '',
      actorDisplayName: json['actor_display_name'] as String? ?? '',
      entityName: json['entity_name'] as String? ?? '',
      entityId: json['entity_id'] as String? ?? '',
      entityDisplayName: json['entity_display_name'] as String? ?? '',
      action: json['action'] as String? ?? '',
      performedAt: json['performed_at'] != null
          ? DateTime.parse(json['performed_at'] as String)
          : DateTime.now(),
    );
  }
}

class OperationsSnapshotResponse {
  final OrderPipelineResponse orders;
  final int openComplaints;
  final int lowStockCount;
  final InvoiceSnapshotResponse? invoices;
  final CashSnapshotResponse? cash;
  final int paymentTermsDays;

  OperationsSnapshotResponse({
    required this.orders,
    required this.openComplaints,
    required this.lowStockCount,
    this.invoices,
    this.cash,
    required this.paymentTermsDays,
  });

  factory OperationsSnapshotResponse.fromJson(Map<String, dynamic> json) {
    return OperationsSnapshotResponse(
      orders: OrderPipelineResponse.fromJson(json['orders'] as Map<String, dynamic>? ?? {}),
      openComplaints: json['open_complaints'] as int? ?? 0,
      lowStockCount: json['low_stock_count'] as int? ?? 0,
      invoices: json['invoices'] != null
          ? InvoiceSnapshotResponse.fromJson(json['invoices'] as Map<String, dynamic>)
          : null,
      cash: json['cash'] != null
          ? CashSnapshotResponse.fromJson(json['cash'] as Map<String, dynamic>)
          : null,
      paymentTermsDays: json['payment_terms_days'] as int? ?? 0,
    );
  }
}

class OrderPipelineResponse {
  final int bookingsToday;
  final Map<String, int> openByStatus;
  final int deliveredToday;
  final int failedToday;
  final int pendingCancellations;

  OrderPipelineResponse({
    required this.bookingsToday,
    required this.openByStatus,
    required this.deliveredToday,
    required this.failedToday,
    required this.pendingCancellations,
  });

  factory OrderPipelineResponse.fromJson(Map<String, dynamic> json) {
    return OrderPipelineResponse(
      bookingsToday: json['bookings_today'] as int? ?? 0,
      openByStatus: Map<String, int>.from(json['open_by_status'] ?? {}),
      deliveredToday: json['delivered_today'] as int? ?? 0,
      failedToday: json['failed_today'] as int? ?? 0,
      pendingCancellations: json['pending_cancellations'] as int? ?? 0,
    );
  }
}

class InvoiceSnapshotResponse {
  final int outstandingCount;
  final double outstandingAmount;
  final int overdueCount;
  final double overdueAmount;
  final int onHoldCount;

  InvoiceSnapshotResponse({
    required this.outstandingCount,
    required this.outstandingAmount,
    required this.overdueCount,
    required this.overdueAmount,
    required this.onHoldCount,
  });

  factory InvoiceSnapshotResponse.fromJson(Map<String, dynamic> json) {
    return InvoiceSnapshotResponse(
      outstandingCount: json['outstanding_count'] as int? ?? 0,
      outstandingAmount: double.tryParse(json['outstanding_amount']?.toString() ?? '0') ?? 0.0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      overdueAmount: double.tryParse(json['overdue_amount']?.toString() ?? '0') ?? 0.0,
      onHoldCount: json['on_hold_count'] as int? ?? 0,
    );
  }
}

class CashSnapshotResponse {
  final double awaitingHandover;
  final int handoversAwaitingReview;

  CashSnapshotResponse({
    required this.awaitingHandover,
    required this.handoversAwaitingReview,
  });

  factory CashSnapshotResponse.fromJson(Map<String, dynamic> json) {
    return CashSnapshotResponse(
      awaitingHandover: double.tryParse(json['awaiting_handover']?.toString() ?? '0') ?? 0.0,
      handoversAwaitingReview: json['handovers_awaiting_review'] as int? ?? 0,
    );
  }
}

class ReviewCashHandoverRequest {
  final String outcome; // 'accepted' or 'disputed'
  final String? note;

  ReviewCashHandoverRequest({
    required this.outcome,
    this.note,
  });

  Map<String, dynamic> toJson() => {
        'outcome': outcome,
        if (note != null) 'note': note,
      };
}

class VerifyKycDocumentRequest {
  final bool approved;
  final String? rejectionReason;

  VerifyKycDocumentRequest({
    required this.approved,
    this.rejectionReason,
  });

  Map<String, dynamic> toJson() => {
        'approved': approved,
        if (rejectionReason != null) 'rejection_reason': rejectionReason,
      };
}
