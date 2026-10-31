import 'package:admin_app/src/features/orders/presentation/order_settlement.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final _order = OrderResponse(
  id: 'o1',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(
    addressLine: 'Flat 4, Shanti Apartments, Pune',
  ),
  status: 'closed',
  bookingSource: 'staff',
  requestedDate: DateTime(2026, 10, 29),
  metadata: const {},
  totalAmount: 905.5,
  lines: const [],
);

final _proof = ProofOfDelivery(
  id: 'p1',
  recordedAt: DateTime.utc(2026, 10, 29, 9, 30),
  paymentMethod: 'cash',
  amountCollected: 905.5,
  gpsLat: 18.52,
  gpsLng: 73.85,
  dacCode: '123456',
);

InvoiceResponse _invoice({double due = 45.28}) => InvoiceResponse(
  invoiceId: 'inv-1',
  invoiceNumber: 'INV-2026-000013',
  tenantId: 't1',
  customerId: 'c1',
  orderId: 'o1',
  status: due > 0 ? 'partially_paid' : 'paid',
  issuedAt: DateTime(2026, 10, 29),
  lines: const [],
  subtotal: 905.5,
  taxAmount: 45.28,
  totalAmount: 950.78,
  version: 1,
  amountPaid: 950.78 - due,
  balanceDue: due,
  customerName: 'E2E Customer',
);

Widget _app(OrderSettlementData data) => ProviderScope(
  overrides: [orderSettlementProvider.overrideWith((ref, id) async => data)],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: Scaffold(
      body: SingleChildScrollView(child: OrderSettlement(order: _order)),
    ),
  ),
);

Future<void> _tall(WidgetTester tester) async {
  tester.view.physicalSize = const Size(800, 3200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  testWidgets('shows the delivery record and the invoice side by side', (
    tester,
  ) async {
    await _tall(tester);
    await tester.pumpWidget(
      _app(OrderSettlementData(proof: _proof, invoice: _invoice())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Delivery'), findsOneWidget);
    expect(find.text('Collected at the door'), findsOneWidget);
    expect(find.text('₹905.50'), findsWidgets);
    expect(find.text('Cash'), findsOneWidget);
    expect(find.text('Open on the map'), findsOneWidget);
    expect(find.text('123456'), findsOneWidget);

    expect(find.text('Payment and invoice'), findsOneWidget);
    expect(find.text('INV-2026-000013'), findsOneWidget);
    expect(find.text('₹950.78'), findsWidgets);
    expect(find.text('₹45.28'), findsWidgets);
    // What the driver collected differs from the invoice: say so plainly.
    expect(find.textContaining('The driver collected ₹905.50'), findsOneWidget);
  });

  testWidgets('a fully paid invoice has nothing to explain', (tester) async {
    await _tall(tester);
    await tester.pumpWidget(
      _app(OrderSettlementData(proof: _proof, invoice: _invoice(due: 0))),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('The driver collected'), findsNothing);
    expect(find.text('Still due'), findsOneWidget);
  });

  testWidgets('says so when there is no invoice', (tester) async {
    await _tall(tester);
    await tester.pumpWidget(_app(OrderSettlementData(proof: _proof)));
    await tester.pumpAndSettle();

    expect(find.text('No invoice for this order yet.'), findsOneWidget);
  });

  testWidgets('an order with no delivery record shows only the payment', (
    tester,
  ) async {
    await _tall(tester);
    await tester.pumpWidget(_app(OrderSettlementData(invoice: _invoice())));
    await tester.pumpAndSettle();

    expect(find.text('Delivery'), findsNothing);
    expect(find.text('Payment and invoice'), findsOneWidget);
  });
}
