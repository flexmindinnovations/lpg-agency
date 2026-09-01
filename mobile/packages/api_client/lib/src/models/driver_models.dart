/// The vehicle a driver is currently out with — mirrors the backend's
/// `DriverMeVehicle`.
class DriverMeVehicle {
  const DriverMeVehicle({
    required this.registrationNumber,
    required this.make,
    required this.model,
  });

  factory DriverMeVehicle.fromJson(Map<String, dynamic> json) => DriverMeVehicle(
    registrationNumber: json['registration_number'] as String,
    make: json['make'] as String,
    model: json['model'] as String,
  );

  final String registrationNumber;
  final String make;
  final String model;

  String get label => '$make $model'.trim();
}

/// The calling driver's own profile — mirrors the backend's
/// `DriverMeResponse` (`GET /drivers/me`). `vehicle` is null when the
/// driver has no active route.
class DriverMe {
  const DriverMe({
    required this.driverId,
    required this.name,
    required this.phoneNumber,
    required this.licenseNumber,
    required this.status,
    this.licenseExpiryDate,
    this.vehicle,
  });

  factory DriverMe.fromJson(Map<String, dynamic> json) => DriverMe(
    driverId: json['driver_id'] as String,
    name: json['name'] as String,
    phoneNumber: json['phone_number'] as String,
    licenseNumber: json['license_number'] as String,
    status: json['status'] as String,
    licenseExpiryDate: json['license_expiry_date'] == null
        ? null
        : DateTime.tryParse(json['license_expiry_date'] as String),
    vehicle: json['vehicle'] == null
        ? null
        : DriverMeVehicle.fromJson(json['vehicle'] as Map<String, dynamic>),
  );

  final String driverId;
  final String name;
  final String phoneNumber;
  final String licenseNumber;
  final String status;
  final DateTime? licenseExpiryDate;
  final DriverMeVehicle? vehicle;
}
