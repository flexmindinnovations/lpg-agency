/// A driver the office can put on a trip — mirrors the backend's
/// `DriverResponse`.
class FleetDriver {
  const FleetDriver({
    required this.id,
    required this.branchId,
    required this.name,
    required this.status,
  });

  factory FleetDriver.fromJson(Map<String, dynamic> json) => FleetDriver(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    name: (json['name'] as String?) ?? 'Driver',
    status: json['status'] as String,
  );

  final String id;
  final String branchId;
  final String name;
  final String status;

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
  });

  factory FleetVehicle.fromJson(Map<String, dynamic> json) => FleetVehicle(
    id: json['id'] as String,
    branchId: json['branch_id'] as String,
    registrationNumber: json['registration_number'] as String,
    capacityUnits: (json['capacity_units'] as num?)?.toInt() ?? 0,
    status: json['status'] as String,
  );

  final String id;
  final String branchId;
  final String registrationNumber;
  final int capacityUnits;
  final String status;

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
