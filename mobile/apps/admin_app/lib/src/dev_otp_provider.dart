import 'package:api_client/api_client.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers.dart';

const showDevOtp = bool.fromEnvironment(
  'SHOW_DEV_OTP',
  defaultValue: kDebugMode,
);

typedef DevOtpLookup = Future<String?> Function(String phoneNumber);

final devOtpLookupProvider = Provider<DevOtpLookup>(
  (ref) => (phoneNumber) async {
    if (!showDevOtp) return null;
    try {
      final result = await AuthApi(
        ref.read(apiClientProvider).dio,
      ).fetchDevOtp(phoneNumber: phoneNumber);
      return result.when<String?>(
        onSuccess: (code) => code,
        onFailure: (_) => null,
      );
    } catch (_) {
      return null;
    }
  },
);
