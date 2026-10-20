import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PhoneNumbers.normalize', () {
    test('turns the ways Indians type a mobile number into E.164', () {
      for (final input in [
        '9999900098',
        '99999 00098',
        '09999900098',
        '919999900098',
        '+919999900098',
        '+91 99999-00098',
      ]) {
        expect(PhoneNumbers.normalize(input), '+919999900098', reason: input);
      }
    });

    test('keeps other international numbers as given', () {
      expect(PhoneNumbers.normalize('+44 20 7946 0958'), '+442079460958');
    });

    test('rejects what cannot be a phone number', () {
      for (final input in ['', '12345', '5999900098', 'abc9999900098', '+1']) {
        expect(PhoneNumbers.normalize(input), isNull, reason: input);
      }
    });
  });
}
