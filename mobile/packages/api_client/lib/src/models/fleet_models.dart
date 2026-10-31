/// A driver the office can put on a trip — mirrors the backend's
/// `DriverResponse`.
class FleetDriver {
  const FleetDriver({
    required this.id,
    required this.branchId,
    required this.name,
    required this.status,
    this.employeeId,
    this.phoneNumber,
    this.licenseNumber,
    this.licenseExpiryDate,
    this.identityUserId,
  });

  factory FleetDriver.fromJson(Map<String, dynamic> json) => FleetDriver(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    name: (json['name'] as String?) ?? 'Driver',
    status: json['status'] as String,
    employeeId: json['employee_id'] as String?,
    phoneNumber: json['phone_number'] as String?,
    licenseNumber: json['license_number'] as String?,
    licenseExpiryDate: json['license_expiry_date'] == null
        ? null
        : DateTime.tryParse(json['license_expiry_date'] as String),
    identityUserId: json['identity_user_id'] as String?,
  );

  final String id;
  final String branchId;
  final String name;
  final String status;
  final String? employeeId;
  final String? phoneNumber;
  final String? licenseNumber;
  final DateTime? licenseExpiryDate;

  /// The Driver App login linked to this driver; null until it is enabled.
  final String? identityUserId;

  bool get hasLogin => identityUserId != null;

  bool get isActive => status == 'active';
}

/// A van — mirrors the backend's `VehicleResponse`.
class FleetVehicle {
  const FleetVehicle({
    required this.id,
    required this.branchId,
    required this.registrationNumber,
    required this.capacityUnits,
    required this.status,
    this.make = '',
    this.model = '',
    this.ownershipType = 'owned',
  });

  factory FleetVehicle.fromJson(Map<String, dynamic> json) => FleetVehicle(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    registrationNumber: json['registration_number'] as String,
    capacityUnits: (json['capacity_units'] as num?)?.toInt() ?? 0,
    status: json['status'] as String,
    make: (json['make'] as String?) ?? '',
    model: (json['model'] as String?) ?? '',
    ownershipType: (json['ownership_type'] as String?) ?? 'owned',
  );

  final String id;
  final String branchId;
  final String registrationNumber;
  final int capacityUnits;
  final String status;
  final String make;
  final String model;
  final String ownershipType;

  bool get isActive => status == 'active';
}

/// A godown — mirrors the backend's admin `WarehouseResponse`.
class FleetWarehouse {
  const FleetWarehouse({
    required this.id,
    required this.branchId,
    required this.name,
    required this.isActive,
  });

  factory FleetWarehouse.fromJson(Map<String, dynamic> json) => FleetWarehouse(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    name: json['name'] as String,
    isActive: json['is_active'] as bool,
  );

  final String id;
  final String branchId;
  final String name;
  final bool isActive;
}

/// A branch — mirrors the backend's admin `BranchResponse`.
class FleetBranch {
  const FleetBranch({
    required this.id,
    required this.name,
    required this.isActive,
  });

  factory FleetBranch.fromJson(Map<String, dynamic> json) => FleetBranch(
    id: json['id'] as String,
    name: json['name'] as String,
    isActive: (json['is_active'] as bool?) ?? true,
  );

  final String id;
  final String name;
  final bool isActive;
}

/// A staff member — mirrors the backend's `EmployeeResponse`. The driver
/// flow picks one with role `driver` or registers a new one.
class FleetEmployee {
  const FleetEmployee({
    required this.id,
    required this.branchId,
    required this.employeeCode,
    required this.firstName,
    required this.lastName,
    required this.phoneNumber,
    required this.role,
    required this.status,
  });

  factory FleetEmployee.fromJson(Map<String, dynamic> json) => FleetEmployee(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    employeeCode: (json['employee_code'] as String?) ?? '',
    firstName: json['first_name'] as String,
    lastName: json['last_name'] as String,
    phoneNumber: (json['phone_number'] as String?) ?? '',
    role: json['role'] as String,
    status: (json['status'] as String?) ?? 'active',
  );

  final String id;
  final String branchId;
  final String employeeCode;
  final String firstName;
  final String lastName;
  final String phoneNumber;
  final String role;
  final String status;

  String get fullName => '$firstName $lastName'.trim();
}

/// Best-effort OCR read of a driving licence or RC photo
/// (`POST /documents/recognize`) — a head start the user reviews, never
/// written through as is.
class RecognizedComplianceDocument {
  const RecognizedComplianceDocument({
    this.confidence = 0,
    this.documentNumber,
    this.validTill,
    this.registrationNumber,
    this.makerModel,
    this.insuranceUpto,
  });

  factory RecognizedComplianceDocument.fromJson(Map<String, dynamic> json) {
    DateTime? date(String key) =>
        json[key] == null ? null : DateTime.tryParse(json[key] as String);
    return RecognizedComplianceDocument(
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      documentNumber: json['document_number'] as String?,
      // A licence's transport validity is the one that matters for driving
      // a commercial van, so it wins over the plain validity when present.
      validTill: date('transport_valid_till') ?? date('valid_till'),
      registrationNumber: json['registration_number'] as String?,
      makerModel: json['maker_model'] as String?,
      insuranceUpto: date('insurance_upto'),
    );
  }

  final double confidence;
  final String? documentNumber;
  final DateTime? validTill;
  final String? registrationNumber;
  final String? makerModel;
  final DateTime? insuranceUpto;
}

/// One line of a location's stock — a cylinder type in one status.
class StockBalanceLine {
  const StockBalanceLine({
    required this.cylinderTypeId,
    required this.status,
    required this.quantity,
  });

  factory StockBalanceLine.fromJson(Map<String, dynamic> json) =>
      StockBalanceLine(
        cylinderTypeId: json['cylinder_type_id'] as String,
        status: json['status'] as String,
        quantity: (json['quantity'] as num).toInt(),
      );

  final String cylinderTypeId;
  final String status;
  final int quantity;
}

/// A physical count against the tracked balance — mirrors
/// `ReconciliationRecordResponse`.
class ReconciliationRecord {
  const ReconciliationRecord({
    required this.id,
    required this.cylinderTypeId,
    required this.status,
    required this.expectedQuantity,
    required this.actualQuantity,
    required this.variance,
    required this.state,
    this.recordedAt,
  });

  factory ReconciliationRecord.fromJson(Map<String, dynamic> json) =>
      ReconciliationRecord(
        id: json['id'] as String,
        cylinderTypeId: json['cylinder_type_id'] as String,
        status: json['status'] as String,
        expectedQuantity: (json['expected_quantity'] as num).toInt(),
        actualQuantity: (json['actual_quantity'] as num).toInt(),
        variance: (json['variance'] as num).toInt(),
        state: (json['state'] as String?) ?? 'pending',
        recordedAt: json['recorded_at'] == null
            ? null
            : DateTime.tryParse(json['recorded_at'] as String),
      );

  final String id;
  final String cylinderTypeId;
  final String status;
  final int expectedQuantity;
  final int actualQuantity;
  final int variance;

  /// `pending`, `approved` or `rejected`.
  final String state;
  final DateTime? recordedAt;

  bool get isPending => state == 'pending';
}

/// A cylinder type that has fallen to or below its reorder point at a godown
/// — mirrors `ReorderSignalResponse` (`GET /inventory/reorder-signals`).
class ReorderSignal {
  const ReorderSignal({
    required this.warehouseId,
    required this.cylinderTypeId,
    required this.onHand,
    required this.reorderPoint,
    required this.safetyStock,
  });

  factory ReorderSignal.fromJson(Map<String, dynamic> json) => ReorderSignal(
    warehouseId: json['location_ref_id'] as String,
    cylinderTypeId: json['cylinder_type_id'] as String,
    onHand: (json['on_hand'] as num).toInt(),
    reorderPoint: (json['reorder_point'] as num).toInt(),
    safetyStock: (json['safety_stock'] as num).toInt(),
  );

  final String warehouseId;
  final String cylinderTypeId;

  /// Filled cylinders now at the godown.
  final int onHand;
  final int reorderPoint;
  final int safetyStock;

  /// At or below the safety stock: not just time to reorder, but nearly out.
  bool get isCritical => onHand <= safetyStock;
}

/// One movement in a location's history — mirrors
/// `InventoryTransactionResponse`.
class InventoryTransaction {
  const InventoryTransaction({
    required this.id,
    required this.cylinderTypeId,
    required this.type,
    required this.toStatus,
    required this.quantity,
    required this.performedAt,
    this.fromStatus,
    this.reason,
  });

  factory InventoryTransaction.fromJson(Map<String, dynamic> json) =>
      InventoryTransaction(
        id: json['id'] as String,
        cylinderTypeId: json['cylinder_type_id'] as String,
        type: json['transaction_type'] as String,
        fromStatus: json['from_status'] as String?,
        toStatus: json['to_status'] as String,
        quantity: (json['quantity'] as num).toInt(),
        reason: json['reason'] as String?,
        performedAt: DateTime.parse(json['performed_at'] as String),
      );

  final String id;
  final String cylinderTypeId;

  /// `grn_receipt`, `load`, `delivery`, `adjustment`, `reconciliation`, …
  final String type;
  final String? fromStatus;
  final String toStatus;
  final int quantity;
  final String? reason;
  final DateTime performedAt;
}

/// A recorded goods receipt note — mirrors `GoodsReceiptResponse`.
class GoodsReceipt {
  const GoodsReceipt({
    required this.id,
    required this.cylinderTypeId,
    required this.quantity,
    this.grnNumber,
  });

  factory GoodsReceipt.fromJson(Map<String, dynamic> json) => GoodsReceipt(
    id: json['id'] as String,
    grnNumber: json['grn_number'] as String?,
    cylinderTypeId: json['cylinder_type_id'] as String,
    quantity: (json['quantity_received'] as num).toInt(),
  );

  final String id;
  final String? grnNumber;
  final String cylinderTypeId;
  final int quantity;
}

/// A licence, certificate or policy kept on file for a driver, van, godown
/// or the agency, mirroring `ComplianceDocumentResponse`.
class ComplianceDocument {
  const ComplianceDocument({
    required this.id,
    required this.ownerType,
    required this.ownerId,
    required this.docType,
    required this.documentNumber,
    required this.verificationStatus,
    this.fileUrl,
    this.issueDate,
    this.expiryDate,
    this.rejectionReason,
  });

  factory ComplianceDocument.fromJson(Map<String, dynamic> json) {
    DateTime? date(String key) =>
        json[key] == null ? null : DateTime.tryParse(json[key] as String);
    return ComplianceDocument(
      id: json['id'] as String,
      ownerType: json['owner_type'] as String,
      ownerId: json['owner_id'] as String,
      docType: json['doc_type'] as String,
      documentNumber: json['document_number'] as String,
      fileUrl: json['file_url'] as String?,
      issueDate: date('issue_date'),
      expiryDate: date('expiry_date'),
      verificationStatus: json['verification_status'] as String,
      rejectionReason: json['rejection_reason'] as String?,
    );
  }

  final String id;

  /// `driver`, `vehicle`, `warehouse` or `tenant`.
  final String ownerType;
  final String ownerId;

  /// `driving_licence`, `vehicle_insurance`, `peso_form_f`, and so on.
  final String docType;
  final String documentNumber;
  final String? fileUrl;
  final DateTime? issueDate;
  final DateTime? expiryDate;

  /// `pending`, `verified` or `rejected`.
  final String verificationStatus;
  final String? rejectionReason;

  /// Whole days from [today] to the expiry date (negative once it has
  /// lapsed); `null` when the document carries no expiry.
  int? daysLeft([DateTime? today]) {
    final expiry = expiryDate;
    if (expiry == null) return null;
    final now = today ?? DateTime.now();
    return DateTime.utc(
      expiry.year,
      expiry.month,
      expiry.day,
    ).difference(DateTime.utc(now.year, now.month, now.day)).inDays;
  }
}

/// Which status each status may move to, as the server enforces it
/// (`GET /inventory/status-transitions`), so the app never offers a move
/// that would be refused. [statusChange] is for ordinary moves (filled to
/// leaking); [adjustment] for manual corrections.
class StatusTransitions {
  const StatusTransitions({
    required this.statusChange,
    required this.adjustment,
  });

  factory StatusTransitions.fromJson(Map<String, dynamic> json) {
    Map<String, List<String>> read(Object? raw) => {
      for (final e in (raw as Map<String, dynamic>? ?? const {}).entries)
        e.key: [for (final v in e.value as List<dynamic>) v as String],
    };
    return StatusTransitions(
      statusChange: read(json['status_change']),
      adjustment: read(json['adjustment']),
    );
  }

  final Map<String, List<String>> statusChange;
  final Map<String, List<String>> adjustment;
}

/// Cylinders sent back to an oil company's plant, mirroring
/// `OmcReturnResponse`.
class OmcReturn {
  const OmcReturn({
    required this.id,
    required this.returnNumber,
    required this.quantity,
    required this.status,
    required this.destinationOmc,
  });

  factory OmcReturn.fromJson(Map<String, dynamic> json) => OmcReturn(
    id: json['id'] as String,
    returnNumber: json['return_number'] as String,
    quantity: (json['quantity'] as num).toInt(),
    status: json['status'] as String,
    destinationOmc: json['destination_omc'] as String,
  );

  final String id;
  final String returnNumber;
  final int quantity;
  final String status;
  final String destinationOmc;
}
