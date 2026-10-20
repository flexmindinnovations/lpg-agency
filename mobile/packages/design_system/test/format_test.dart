import 'package:design_system/design_system.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('LpgFormat.orderNumber', () {
    test('shows the order number the dashboard uses', () {
      expect(
        LpgFormat.orderNumber('ORD000027', '4c6826f9-9d69-4747-a6ca'),
        'ORD000027',
      );
    });

    test('falls back to a short id when the number is missing', () {
      expect(
        LpgFormat.orderNumber(null, '4c6826f9-9d69-4747-a6ca'),
        '#4C6826F9',
      );
      expect(LpgFormat.orderNumber('', 'abc'), '#ABC');
    });
  });
}
