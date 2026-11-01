import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/presentation/order_presentation.dart';
import 'package:flutter_test/flutter_test.dart';

OrderResponse _order(String status, {String? preference}) => OrderResponse(
  id: 'o1',
  tenantId: 't',
  branchId: 'b',
  customerId: 'c',
  addressId: 'a',
  deliveryAddress: const DeliveryAddressPayload(addressLine: 'x'),
  status: status,
  bookingSource: 'mobile_app',
  paymentMethodPreference: preference,
  requestedDate: DateTime(2026, 11, 1),
  metadata: const {},
  lines: const [],
);

void main() {
  group('which actions an order offers', () {
    test('cancel follows the backend state machine', () {
      for (final s in [
        'booked',
        'confirmed',
        'assigned',
        'ready_for_dispatch',
      ]) {
        expect(_order(s).canCancel, isTrue, reason: s);
        expect(_order(s).cancelNeedsApproval, isFalse, reason: s);
      }
      expect(_order('out_for_delivery').canCancel, isTrue);
      expect(_order('out_for_delivery').cancelNeedsApproval, isTrue);
      for (final s in [
        'draft',
        'delivered',
        'closed',
        'cancelled',
        'failed_delivery',
      ]) {
        expect(_order(s).canCancel, isFalse, reason: s);
      }
    });

    test('prepaying is offered only before delivery', () {
      for (final s in [
        'confirmed',
        'assigned',
        'ready_for_dispatch',
        'out_for_delivery',
      ]) {
        expect(_order(s).canPrepay, isTrue, reason: s);
      }
      for (final s in [
        'booked',
        'delivered',
        'closed',
        'cancelled',
        'failed_delivery',
      ]) {
        expect(_order(s).canPrepay, isFalse, reason: s);
      }
    });

    test('a credit-account order is never asked to prepay', () {
      expect(_order('confirmed', preference: 'credit').canPrepay, isFalse);
      expect(
        _order('confirmed', preference: 'credit').isBilledOnCredit,
        isTrue,
      );
      expect(_order('confirmed', preference: 'cash').canPrepay, isTrue);
    });
  });
}
