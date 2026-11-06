import 'package:dio/dio.dart';

import 'device_identity.dart';

/// Error codes that mean "this phone is not allowed in right now".
const deviceErrorCodes = {
  'DEVICE_PENDING',
  'DEVICE_BLOCKED',
  'DEVICE_REMOVED',
  'DEVICE_REQUIRED',
};

/// Paths whose request bodies carry the `device` object.
const _deviceBodyPaths = ['/auth/login', '/auth/otp/verify', '/auth/refresh'];

/// Dio interceptor that makes every request identify its phone (ADR-071) and
/// reports when the server refuses the phone.
///
/// - Adds `X-Device-Id` and `X-App-Type` to every request, so the server can
///   check the phone on each call.
/// - On sign-in, OTP verify and refresh, adds the phone's details as the
///   body's `device` object, so the server can register it. Doing it here
///   keeps the shared auth code unchanged.
/// - Passes a `DEVICE_*` refusal to [onRefused] and lets the error carry on
///   (callers still see the failure).
///
/// Added to `ApiClient.dio.interceptors` once, at start-up. The client's
/// refresh-and-retry re-runs this interceptor, so retried calls keep the
/// headers.
final class DeviceInterceptor extends Interceptor {
  DeviceInterceptor({required this.identity, required this.onRefused});

  final DeviceIdentity identity;

  /// Called with the refusal's `error_code` (for example `DEVICE_BLOCKED`).
  final void Function(String errorCode) onRefused;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.headers.addAll(identity.headers);

    final data = options.data;
    if (data is Map<String, dynamic> &&
        _deviceBodyPaths.any(options.path.endsWith)) {
      options.data = {...data, 'device': identity.authBody};
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final code = deviceErrorCode(err);
    if (code != null) {
      // The refresh-and-retry path runs this interceptor too, so a 401
      // DEVICE_REQUIRED that the retry then fixes never reaches here; one that
      // still fails afterwards is a real refusal.
      onRefused(code);
    }
    handler.next(err);
  }
}

/// The `DEVICE_*` error code in a failed response, or `null`.
String? deviceErrorCode(DioException error) {
  final data = error.response?.data;
  if (data is Map && data['error_code'] is String) {
    final code = data['error_code'] as String;
    if (deviceErrorCodes.contains(code)) return code;
  }
  return null;
}
