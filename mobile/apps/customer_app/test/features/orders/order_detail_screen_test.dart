import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/orders/presentation/order_detail_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

OrderResponse _order({String status = 'confirmed'}) => OrderResponse(
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
  totalAmount: 999,
  lines: const [
    OrderLineResponse(
      id: 'l1',
      cylinderTypeId: 'ct1',
      quantityOrdered: 2,
      quantityDelivered: 0,
      quantityPending: 2,
      quantityCollectedEmpty: 0,
      isBackordered: false,
      unitPrice: 499.5,
    ),
  ],
);

Widget _screen({OrderResponse? order, Object? error}) => ProviderScope(
  overrides: [
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
    testWidgets('renders the order status and delivery address', (tester) async {
      await pumpScreen(tester, _screen(order: _order()));

      expect(find.text('Order Details'), findsOneWidget);
      expect(find.text('12 Baker Street, Marylebone'), findsOneWidget);
      expect(find.textContaining('CONFIRMED'), findsWidgets);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('boom')));

      expect(find.textContaining('Failed to load this order'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
