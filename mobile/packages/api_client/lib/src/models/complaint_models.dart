/// Values for [ComplaintResponse.category] — mirrors the backend's
/// `ComplaintCategory` (`domain/complaint/value_objects.py`). Kept as plain
/// `String` constants rather than a Dart `enum`, matching every other
/// status-like field in this package (`OrderResponse.status` etc.): a
/// server-added value should never crash `fromJson`.
abstract final class ComplaintCategory {
  static const shortDelivery = 'ShortDelivery';
  static const damagedCylinder = 'DamagedCylinder';
  static const billingDispute = 'BillingDispute';
  static const driverConduct = 'DriverConduct';
  static const lateDelivery = 'LateDelivery';
  static const other = 'Other';
}

/// Values for [ComplaintResponse.priority] — mirrors `ComplaintPriority`.
abstract final class ComplaintPriority {
  static const low = 'Low';
  static const medium = 'Medium';
  static const high = 'High';
  static const critical = 'Critical';
}

/// Values for [ComplaintResponse.status] — mirrors `ComplaintStatus`.
abstract final class ComplaintStatus {
  static const open = 'Open';
  static const assigned = 'Assigned';
  static const inProgress = 'InProgress';
  static const resolved = 'Resolved';
  static const rejected = 'Rejected';
  static const closed = 'Closed';
}

/// Mirrors the backend's `ComplaintAssignmentResponse`.
class ComplaintAssignmentResponse {
  const ComplaintAssignmentResponse({
    required this.id,
    required this.assignedTo,
    required this.assignedAt,
    required this.createdAt,
    this.createdBy,
  });

  factory ComplaintAssignmentResponse.fromJson(Map<String, dynamic> json) =>
      ComplaintAssignmentResponse(
        id: json['id'] as String,
        assignedTo: json['assigned_to'] as String,
        assignedAt: DateTime.parse(json['assigned_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        createdBy: json['created_by'] as String?,
      );

  final String id;
  final String assignedTo;
  final DateTime assignedAt;
  final DateTime createdAt;
  final String? createdBy;
}

/// Mirrors the backend's `ComplaintResolutionResponse`. `outcome` is one of
/// `ResolutionOutcome`'s values (`Resolved`/`Compensated`/`Rejected`).
class ComplaintResolutionResponse {
  const ComplaintResolutionResponse({
    required this.id,
    required this.outcome,
    required this.resolutionNotes,
    required this.resolvedBy,
    required this.resolvedAt,
    required this.createdAt,
  });

  factory ComplaintResolutionResponse.fromJson(Map<String, dynamic> json) =>
      ComplaintResolutionResponse(
        id: json['id'] as String,
        outcome: json['outcome'] as String,
        resolutionNotes: json['resolution_notes'] as String,
        resolvedBy: json['resolved_by'] as String,
        resolvedAt: DateTime.parse(json['resolved_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final String id;
  final String outcome;
  final String resolutionNotes;
  final String resolvedBy;
  final DateTime resolvedAt;
  final DateTime createdAt;
}

/// Mirrors the backend's `ComplaintResponse`.
class ComplaintResponse {
  const ComplaintResponse({
    required this.id,
    this.complaintNumber,
    required this.customerId,
    this.orderId,
    required this.category,
    required this.priority,
    required this.status,
    required this.description,
    this.slaDueAt,
    required this.createdAt,
    required this.updatedAt,
    this.createdBy,
    this.updatedBy,
    this.assignments = const [],
    this.resolution,
  });

  factory ComplaintResponse.fromJson(Map<String, dynamic> json) =>
      ComplaintResponse(
        id: json['id'] as String,
        complaintNumber: json['complaint_number'] as String?,
        customerId: json['customer_id'] as String,
        orderId: json['order_id'] as String?,
        category: json['category'] as String,
        priority: json['priority'] as String,
        status: json['status'] as String,
        description: json['description'] as String,
        slaDueAt: json['sla_due_at'] == null
            ? null
            : DateTime.parse(json['sla_due_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
        createdBy: json['created_by'] as String?,
        updatedBy: json['updated_by'] as String?,
        assignments:
            (json['assignments'] as List<dynamic>?)
                ?.map(
                  (e) => ComplaintAssignmentResponse.fromJson(
                    e as Map<String, dynamic>,
                  ),
                )
                .toList() ??
            const [],
        resolution: json['resolution'] == null
            ? null
            : ComplaintResolutionResponse.fromJson(
                json['resolution'] as Map<String, dynamic>,
              ),
      );

  final String id;
  final String? complaintNumber;
  final String customerId;
  final String? orderId;
  final String category;
  final String priority;
  final String status;
  final String description;
  final DateTime? slaDueAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? createdBy;
  final String? updatedBy;
  final List<ComplaintAssignmentResponse> assignments;
  final ComplaintResolutionResponse? resolution;
}

/// `GET /complaints` pagination wrapper — mirrors the backend's
/// `ComplaintListResponse`. Note this is `{items, total, skip, limit}`
/// (offset-based), a different shape from [InvoicePageResponse]'s
/// `{items, total, page, page_size}`.
class ComplaintListResponse {
  const ComplaintListResponse({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  factory ComplaintListResponse.fromJson(Map<String, dynamic> json) =>
      ComplaintListResponse(
        items: (json['items'] as List<dynamic>)
            .map((e) => ComplaintResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int,
        skip: json['skip'] as int,
        limit: json['limit'] as int,
      );

  final List<ComplaintResponse> items;
  final int total;
  final int skip;
  final int limit;
}

/// `POST /complaints` body — mirrors the backend's `RaiseComplaintRequest`.
/// `customerId` is required by the schema even though the server overrides
/// it with the signed-in customer's own id for a `customer`-role principal
/// (`complaint.py`'s `_resolve_own_customer_id`) — pass the caller's own id.
class RaiseComplaintRequest {
  const RaiseComplaintRequest({
    required this.customerId,
    required this.category,
    required this.priority,
    required this.description,
    this.orderId,
  });

  final String customerId;
  final String category;
  final String priority;
  final String description;
  final String? orderId;

  Map<String, dynamic> toJson() => {
    'customer_id': customerId,
    'category': category,
    'priority': priority,
    'description': description,
    if (orderId != null) 'order_id': orderId,
  };
}
