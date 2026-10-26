import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('DashboardSummaryResponse parses Decimal fields serialised as strings', () {
    final summary = DashboardSummaryResponse.fromJson({
      'customer_count': 1,
      'driver_count': 2,
      'vehicle_count': 3,
      'vehicles_by_status': {'available': 3},
      'warehouse_count': 1,
      'cylinder_type_count': 1,
      'inventory_by_status': {'full': 10},
      'price_cards': [
        {
          'cylinder_type_id': 'c1',
          'name': '14.2 kg',
          'weight_kg': '14.20',
          'customer_type': 'domestic',
          'price': '905.50',
        },
      ],
      'recent_activity': [],
    });
    expect(summary.priceCards.single.weightKg, 14.2);
    expect(summary.priceCards.single.price, 905.5);
  });

  test('Principal reads display_name and email', () {
    final p = Principal.fromJson({
      'user_id': 'u',
      'tenant_id': 't',
      'role': 'admin',
      'permissions': <String>[],
      'display_name': 'Asha Rao',
      'email': 'a@x.com',
    });
    expect(p.displayName, 'Asha Rao');
    expect(p.email, 'a@x.com');
  });
}
