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
