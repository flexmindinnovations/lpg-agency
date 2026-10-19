import 'package:api_client/api_client.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_provider.dart';

/// Whether the login and Record delivery screens may display OTPs on screen.
///
/// TEMPORARY, for testing only: there is no SMS/WhatsApp gateway yet, so a
/// tester has no other way to see the code. Defaults to on in debug builds
/// and off in release builds; override with
/// `--dart-define=SHOW_DEV_OTP=true|false`. Remove this file, the login
/// screen's banner and `AuthApi.fetchDevOtp` once a real gateway is wired.
const showDevOtp = bool.fromEnvironment(
  'SHOW_DEV_OTP',
  defaultValue: kDebugMode,
);

/// Looks up the OTP just requested for a phone number, or `null` when there
/// is nothing to show (feature off, backend in production, no code pending).
typedef DevOtpLookup = Future<String?> Function(String phoneNumber);

final devOtpLookupProvider = Provider<DevOtpLookup>(
  (ref) => (phoneNumber) async {
    if (!showDevOtp) return null;
    try {
      final result = await AuthApi(
        ref.read(apiClientProvider).dio,
      ).fetchDevOtp(phoneNumber: phoneNumber);
      final code = result.when(
        onSuccess: (code) => code,
        onFailure: (_) => null,
      );
      return code;
    } on Object {
      // Best effort: the driver can still type the code from elsewhere.
      return null;
    }
  },
);

/// Looks up the delivery OTP last sent to an order's customer, or `null`
/// when there is nothing to show (feature off, backend in production, no
/// code pending). Same testing-only rules as [devOtpLookupProvider].
typedef DevDeliveryOtpLookup = Future<String?> Function(String orderId);

final devDeliveryOtpLookupProvider = Provider<DevDeliveryOtpLookup>(
  (ref) => (orderId) async {
    if (!showDevOtp) return null;
    try {
      final result = await ref
          .read(orderApiProvider)
          .fetchDevDeliveryOtp(orderId);
      final code = result.when<String?>(
        onSuccess: (code) => code,
        onFailure: (_) => null,
      );
      return code;
    } on Object {
      return null;
    }
  },
);
