import 'package:admin_app/src/features/orders/domain/order_booking.dart';
import 'package:admin_app/src/features/orders/domain/order_flow.dart';
import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

CustomerAddressResponse _address(String id, {bool primary = false}) =>
    CustomerAddressResponse.fromJson({
      'id': id,
      'line_1': '12 MG Road',
      'city': 'Pune',
      'is_primary': primary,
      'address_type': 'home',
    });

CustomerResponse _customer(List<CustomerAddressResponse> addresses) =>
    CustomerResponse.fromJson({
      'id': 'c1',
      'tenant_id': 't',
      'branch_id': 'b1',
      'full_name': 'Asha',
      'phone_number': '+919800000000',
      'customer_type': 'domestic',
      'kyc_status': 'verified',
      'status': 'active',
      'addresses': [
        for (final a in addresses)
          {
            'id': a.id,
            'line_1': a.line1,
            'city': a.city,
            'is_primary': a.isPrimary,
            'address_type': 'home',
          },
      ],
    });

OrderableCylinderTypeResponse _type(String id, int stock) =>
    OrderableCylinderTypeResponse(
      cylinderTypeId: id,
      name: 'Domestic 14.2 kg',
      weightKg: 14.2,
      unitPrice: 900,
      availableQuantity: stock,
    );

void main() {
  final customer = _customer([_address('a1', primary: true)]);
  final orderable = [_type('t1', 5), _type('t2', 1)];

  group('bookingProblem', () {
    String? problem({
      CustomerResponse? c,
      String? address = 'a1',
      List<BookingLine> lines = const [
        BookingLine(cylinderTypeId: 't1', quantity: 2),
      ],
    }) => bookingProblem(
      customer: c ?? customer,
      addressId: address,
      lines: lines,
      orderable: orderable,
    );

    test('a complete booking has no problem', () {
      expect(problem(), isNull);
    });

    test('needs a customer, an address and a cylinder type', () {
      expect(
        bookingProblem(
          customer: null,
          addressId: null,
          lines: const [],
          orderable: orderable,
        ),
        'Select a customer.',
      );
      expect(problem(address: null), 'Select a delivery address.');
      expect(
        problem(lines: const [BookingLine()]),
        'Select a cylinder type for every line.',
      );
    });

    test('a customer with no saved address cannot be booked', () {
      expect(problem(c: _customer([])), contains('no saved address'));
    });

    test('quantity is at least 1 and no more than the stock left', () {
      expect(
        problem(lines: const [BookingLine(cylinderTypeId: 't1', quantity: 0)]),
        'Quantity must be at least 1.',
      );
      expect(
        problem(lines: const [BookingLine(cylinderTypeId: 't1', quantity: 6)]),
        'Only 5 Domestic 14.2 kg are in stock.',
      );
      expect(
        problem(lines: const [BookingLine(cylinderTypeId: 't2', quantity: 2)]),
        'Only 1 Domestic 14.2 kg is in stock.',
      );
    });

    test('a type cannot repeat, or be one the customer cannot book', () {
      expect(
        problem(
          lines: const [
            BookingLine(cylinderTypeId: 't1'),
            BookingLine(cylinderTypeId: 't1'),
          ],
        ),
        contains('only be on the order once'),
      );
      expect(
        problem(lines: const [BookingLine(cylinderTypeId: 'gone')]),
        contains('can no longer be booked'),
      );
    });
  });

  group('defaultAddress', () {
    test('prefers the primary address', () {
      final c = _customer([_address('a1'), _address('a2', primary: true)]);
      expect(defaultAddress(c)?.id, 'a2');
    });

    test('takes the only address, but never guesses between several', () {
      expect(defaultAddress(_customer([_address('a1')]))?.id, 'a1');
      expect(
        defaultAddress(_customer([_address('a1'), _address('a2')])),
        isNull,
      );
    });
  });

  test('deliveryDay is noon local time on that date', () {
    final day = deliveryDay(DateTime(2026, 10, 30, 23, 59));
    expect(day, DateTime(2026, 10, 30, 12));
  });

  group('weighmentProblem', () {
    test('needs a scale and sensible counts', () {
      expect(
        weighmentProblem(scaleId: null, cylinders: 3, underweight: 0),
        'Choose the scale you used.',
      );
      expect(
        weighmentProblem(scaleId: 's', cylinders: 0, underweight: 0),
        'Enter how many cylinders you weighed.',
      );
      expect(
        weighmentProblem(scaleId: 's', cylinders: 3, underweight: 4),
        contains('More cylinders came up underweight'),
      );
      expect(
        weighmentProblem(scaleId: 's', cylinders: 3, underweight: 1),
        isNull,
      );
    });
  });
}
