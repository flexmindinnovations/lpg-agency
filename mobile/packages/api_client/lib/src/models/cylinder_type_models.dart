import 'decimal_json.dart';

/// Mirrors the backend's `CylinderTypeResponse`
/// (`api/v1/schemas/admin.py` / `admin.py`'s `list_cylinder_types`) — the
/// tenant's cylinder-type catalog (e.g. "14.2kg Domestic",
/// "Commercial 19kg") used to build an order's line items.
class CylinderTypeResponse {
  const CylinderTypeResponse({
    required this.id,
    required this.name,
    required this.weightKg,
    required this.isActive,
  });

  factory CylinderTypeResponse.fromJson(Map<String, dynamic> json) =>
      CylinderTypeResponse(
        id: json['id'] as String,
        name: json['name'] as String,
        weightKg: asDouble(json['weight_kg']),
        isActive: json['is_active'] as bool,
      );

  final String id;
  final String name;
  final double weightKg;
  final bool isActive;
}
