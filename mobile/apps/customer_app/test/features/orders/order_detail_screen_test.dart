import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/cylinder_types_provider.dart';
import 'package:customer_app/src/features/orders/data/invoices_provider.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/orders/presentation/order_detail_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

OrderResponse _order({
  String status = 'confirmed',
  double? totalAmount = 999,
}) => OrderResponse(
  id: 'abcdef01aaaabbbb',
  orderNumber: 'ORD000042',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(
    addressLine: '12 Baker Street, Marylebone',
  ),
  status: status,
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 8, 20, 10, 30),
  metadata: const {},
  totalAmount: totalAmount,
  lines: [
    OrderLineResponse(
      id: 'l1',
      cylinderTypeId: 'ct1',
      quantityOrdered: 2,
      quantityDelivered: 0,
      quantityPending: 2,
      quantityCollectedEmpty: 0,
      isBackordered: false,
      unitPrice: totalAmount == null ? null : 499.5,
    ),
  ],
);

Widget _screen({
  OrderResponse? order,
  Object? error,
  String? deliveryCode,
  PendingCancellationResponse? pendingCancel,
}) => ProviderScope(
  overrides: [
    deliveryCodeProvider.overrideWith((ref, id) async => deliveryCode),
    pendingCancellationProvider.overrideWith((ref, id) async => pendingCancel),
    orderHistoryProvider.overrideWith((ref, id) async => const []),
    cylinderTypeNamesProvider.overrideWith(
      (ref) async => {'ct1': 'Domestic 14.2kg'},
    ),
    orderableCylinderTypesProvider.overrideWith(
      (ref) async => const [
        OrderableCylinderTypeResponse(
          cylinderTypeId: 'ct1',
          name: 'Domestic 14.2kg',
          weightKg: 14.2,
          unitPrice: 905.5,
          availableQuantity: 20,
        ),
      ],
    ),
    invoicesProvider.overrideWith((ref) async => const []),
    orderDetailProvider.overrideWith((ref, id) async {
      if (error != null) throw error;
      return order ?? _order();
    }),
    orderRealtimeProvider.overrideWith(
      (ref, id) => const Stream<Map<String, dynamic>>.empty(),
    ),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const OrderDetailScreen(orderId: 'abcdef01aaaabbbb'),
  ),
);

void main() {
  group('OrderDetailScreen', () {
    testWidgets('renders the order status and delivery address', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(order: _order()));

      expect(find.text('Order Details'), findsOneWidget);
      expect(find.text('12 Baker Street, Marylebone'), findsOneWidget);
      expect(find.textContaining('Confirmed'), findsWidgets);
    });

    testWidgets('offers Cancel Order while the order is still open', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(order: _order(status: 'confirmed')));

      expect(find.text('Cancel Order'), findsOneWidget);
    });

    for (final status in ['delivered', 'closed', 'cancelled', 'draft']) {
      testWidgets('never offers Cancel Order once the order is $status', (
        tester,
      ) async {
        await pumpScreen(tester, _screen(order: _order(status: status)));

        expect(find.text('Cancel Order'), findsNothing);
        expect(find.text('Pay Online'), findsNothing);
      });
    }

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('boom')));

      expect(find.textContaining('Failed to load this order'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('names each cylinder line with its price (CA-06)', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(order: _order()));

      expect(find.text('Domestic 14.2kg × 2'), findsOneWidget);
      expect(find.text('₹999.00'), findsWidgets);
    });

    testWidgets('estimates the total before the agency prices it (CA-06)', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(order: _order(status: 'booked', totalAmount: null)),
      );

      expect(find.text('Estimated total'), findsOneWidget);
      expect(find.text('₹1,811.00'), findsWidgets);
      expect(find.text('Pending'), findsNothing);
    });

    testWidgets('shows the delivery code while out for delivery (CA-04)', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(
          order: _order(status: 'out_for_delivery'),
          deliveryCode: '482913',
        ),
      );

      expect(find.byKey(const Key('delivery-code')), findsOneWidget);
      expect(find.text('482913'), findsOneWidget);
    });

    testWidgets(
      'a pending cancellation replaces Cancel and Pay Online (CA-07)',
      (tester) async {
        await pumpScreen(
          tester,
          _screen(
            order: _order(status: 'out_for_delivery'),
            deliveryCode: '482913',
            pendingCancel: PendingCancellationResponse(
              id: 'c1',
              orderId: 'abcdef01aaaabbbb',
              reason: 'Booked twice',
              requestedAt: DateTime(2026, 10, 20, 9),
            ),
          ),
        );

        expect(find.byKey(const Key('cancellation-pending')), findsOneWidget);
        expect(find.textContaining('Booked twice'), findsOneWidget);
        expect(find.text('Cancel Order'), findsNothing);
        expect(find.text('Pay Online'), findsNothing);
      },
    );

    testWidgets('cancelling with no reason explains why (CA-11)', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(order: _order(status: 'booked')));

      await tester.tap(find.text('Cancel Order'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(LpgButton, 'Cancel Order').last);
      await tester.pumpAndSettle();

      expect(
        find.text('Please tell us why you are cancelling.'),
        findsOneWidget,
      );
      expect(find.text('Cancel this order?'), findsOneWidget);
    });
  });
}
