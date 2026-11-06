import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

void main() {
  test('a generated key decodes to 32 bytes', () {
    expect(hexToBytes(generateEncryptionKey()), hasLength(32));
  });

  test('hex decodes to the bytes it spells', () {
    expect(hexToBytes('00ff10'), [0, 255, 16]);
  });

  test('an odd-length string is rejected', () {
    expect(() => hexToBytes('abc'), throwsFormatException);
  });
}
