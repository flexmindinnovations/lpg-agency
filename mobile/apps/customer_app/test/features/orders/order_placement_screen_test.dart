import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/cylinder_types_provider.dart';
import 'package:customer_app/src/features/orders/presentation/order_placement_screen.dart';
import 'package:customer_app/src/features/profile/data/profile_provider.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

const _profile = CustomerResponse(
  id: 'cust-1',
  tenantId: 't1',
  branchId: 'b1',
  fullName: 'Asha Menon',
  phoneNumber: '+919000000000',
  customerType: 'domestic',
  kycStatus: 'verified',
  status: 'active',
  addresses: [
    CustomerAddressResponse(
      id: 'addr-1',
      line1: '12 MG Road',
      addressType: 'delivery',
      isPrimary: true,
    ),
  ],
);

Widget _screen({ReorderDraft? draft}) => ProviderScope(
  overrides: [
    profileProvider.overrideWith((ref) async => _profile),
    orderableCylinderTypesProvider.overrideWith(
      (ref) async => const [
        OrderableCylinderTypeResponse(
          cylinderTypeId: 'ct-5',
          name: 'Domestic 5kg',
          weightKg: 5,
          unitPrice: 389,
          availableQuantity: 10,
        ),
        OrderableCylinderTypeResponse(
          cylinderTypeId: 'ct-14',
          name: 'Domestic 14.2kg',
          weightKg: 14.2,
          unitPrice: 905.5,
          availableQuantity: 10,
        ),
      ],
    ),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: OrderPlacementScreen(draft: draft),
  ),
);

void main() {
  group('OrderPlacementScreen', () {
    testWidgets('shows the price and total before placing (CA-06)', (
      tester,
    ) async {
      await pumpScreen(tester, _screen());

      await tester.tap(find.text('Domestic 14.2kg'));
      await tester.tap(find.byTooltip('Increase'));
      await tester.pumpAndSettle();

      expect(find.text('2 × Domestic 14.2kg'), findsOneWidget);
      expect(find.byKey(const Key('order-total')), findsOneWidget);
      expect(find.text('₹1,811.00'), findsOneWidget);
    });

    testWidgets('Order Again starts from the earlier order', (tester) async {
      await pumpScreen(
        tester,
        _screen(draft: const ReorderDraft(cylinderTypeId: 'ct-5', quantity: 3)),
      );

      expect(find.text('3 × Domestic 5kg'), findsOneWidget);
      expect(find.text('₹1,167.00'), findsOneWidget);
    });
  });
}
