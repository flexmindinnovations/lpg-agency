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

/// Mirrors the backend's `OrderableCylinderTypeResponse`
/// (`GET /api/v1/orders/orderable-cylinder-types`) — a cylinder type this
/// customer can book right now: active, priced for their customer type at
/// their branch, and in stock. The server refuses a booking for anything
/// else, so order placement offers only these.
class OrderableCylinderTypeResponse {
  const OrderableCylinderTypeResponse({
    required this.cylinderTypeId,
    required this.name,
    required this.weightKg,
    required this.unitPrice,
    required this.availableQuantity,
  });

  factory OrderableCylinderTypeResponse.fromJson(Map<String, dynamic> json) =>
      OrderableCylinderTypeResponse(
        cylinderTypeId: json['cylinder_type_id'] as String,
        name: json['name'] as String,
        weightKg: asDouble(json['weight_kg']),
        unitPrice: asDouble(json['unit_price']),
        availableQuantity: json['available_quantity'] as int,
      );

  final String cylinderTypeId;
  final String name;
  final double weightKg;

  /// Today's price for this customer. The order's price is fixed when the
  /// agency confirms it.
  final double unitPrice;

  /// Filled cylinders the branch can still promise to new bookings.
  final int availableQuantity;
}
