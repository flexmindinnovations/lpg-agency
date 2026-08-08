import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Result', () {
    test('success carries its value', () {
      const result = Success<int>(42);

      final output = result.when(
        onSuccess: (value) => 'ok:$value',
        onFailure: (failure) => 'err:${failure.message}',
      );

      expect(output, 'ok:42');
    });

    test('failure carries its message and error code', () {
      const result = FailureResult<int>(
        Failure(
          message: 'Inventory would go negative',
          errorCode: 'INVARIANT_VIOLATION',
        ),
      );

      final output = result.when(
        onSuccess: (value) => 'ok:$value',
        onFailure: (failure) => '${failure.errorCode}:${failure.message}',
      );

      expect(output, 'INVARIANT_VIOLATION:Inventory would go negative');
    });

    test('both branches must be handled', () {
      // The point of the sealed type: a caller cannot ignore the failure case,
      // which on the Driver App sync path would mean a delivery silently
      // never reaching the server.
      const Result<String> result = FailureResult<String>(
        Failure(message: 'offline'),
      );
      expect(
        result.when(onSuccess: (_) => false, onFailure: (_) => true),
        isTrue,
      );
    });
  });
}
