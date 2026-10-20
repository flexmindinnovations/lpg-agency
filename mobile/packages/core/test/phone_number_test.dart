import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normalizePhoneNumber', () {
    const cases = {
      '9876543210': '+919876543210',
      '09876543210': '+919876543210',
      '919876543210': '+919876543210',
      '+919876543210': '+919876543210',
      ' +91 98765-43210 ': '+919876543210',
      '+14155552671': '+14155552671',
      '12345': '12345',
    };
    cases.forEach((raw, expected) {
      test('"$raw" -> "$expected"', () {
        expect(normalizePhoneNumber(raw), expected);
      });
    });
  });

  test('isValidPhoneNumber accepts E.164 only', () {
    expect(isValidPhoneNumber('+919876543210'), isTrue);
    expect(isValidPhoneNumber('12345'), isFalse);
    expect(isValidPhoneNumber('9876543210'), isFalse);
  });
}
