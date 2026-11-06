import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

Failure _f(String? code) => Failure(message: 'server words', errorCode: code);

void main() {
  group('errorKindOf', () {
    test('maps the transport codes the client produces', () {
      expect(errorKindOf(_f('NETWORK_UNAVAILABLE')), ErrorKind.offline);
      expect(errorKindOf(_f('SERVER_UNAVAILABLE')), ErrorKind.busy);
      expect(errorKindOf(_f('UNEXPECTED_RESPONSE')), ErrorKind.server);
    });

    test('maps the backend codes that exist today', () {
      const expected = {
        'AUTHENTICATION_REQUIRED': ErrorKind.sessionExpired,
        'REFRESH_TOKEN_INVALID': ErrorKind.sessionExpired,
        'PERMISSION_DENIED': ErrorKind.forbidden,
        'TENANT_SUSPENDED': ErrorKind.agencyBlocked,
        'LICENSE_EXPIRED': ErrorKind.agencyBlocked,
        'RESOURCE_NOT_FOUND': ErrorKind.notFound,
        'CYLINDER_UNIT_NOT_FOUND': ErrorKind.notFound,
        'RATE_LIMIT_EXCEEDED': ErrorKind.busy,
        'INTERNAL_SERVER_ERROR': ErrorKind.server,
        'VALIDATION_FAILED': ErrorKind.rejected,
        'DUPLICATE_PHONE': ErrorKind.rejected,
        'INSUFFICIENT_STOCK': ErrorKind.rejected,
        'OTP_MISMATCH': ErrorKind.rejected,
      };
      for (final entry in expected.entries) {
        expect(errorKindOf(_f(entry.key)), entry.value, reason: entry.key);
      }
    });

    test('sees through an exception that wraps a failure', () {
      expect(
        errorKindOf(FailureException(_f('NETWORK_UNAVAILABLE'))),
        ErrorKind.offline,
      );
    });

    test('anything that is not an API failure is unknown', () {
      expect(errorKindOf(StateError('bug')), ErrorKind.unknown);
      expect(errorKindOf(_f(null)), ErrorKind.unknown);
    });
  });

  group('supportCodeOf', () {
    test('shows the server code where the message cannot say more', () {
      expect(supportCodeOf(_f('DUPLICATE_PHONE')), 'DUPLICATE_PHONE');
      expect(
        supportCodeOf(_f('INTERNAL_SERVER_ERROR')),
        'INTERNAL_SERVER_ERROR',
      );
      expect(supportCodeOf(_f('RESOURCE_NOT_FOUND')), 'RESOURCE_NOT_FOUND');
    });

    test('shows nothing where the message is enough', () {
      expect(supportCodeOf(_f('NETWORK_UNAVAILABLE')), isNull);
      expect(supportCodeOf(_f('PERMISSION_DENIED')), isNull);
      expect(supportCodeOf(_f('AUTHENTICATION_REQUIRED')), isNull);
      expect(supportCodeOf(StateError('bug')), isNull);
    });
  });
}
