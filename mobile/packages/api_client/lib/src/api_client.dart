import 'package:dio/dio.dart';

/// `/auth/*` paths that must never be bearer-attached-and-retried by the
/// 401 handler below — the token-issuing endpoints themselves. Mirrors
/// `AUTH_ENDPOINT_SEGMENTS` in the Dashboard's `auth.interceptor.ts`.
const _authEndpointPaths = ['/auth/login', '/auth/refresh', '/auth/otp/verify'];

/// Owns the configured [Dio] instance shared by every hand-written endpoint
/// wrapper in this package (`AuthApi` today; future phases add more).
///
/// Bearer-attaches the current access token on every request (after waiting
/// for [waitForSession], when given, so a request made while the session is
/// still being restored waits instead of failing) and performs
/// one silent refresh-and-retry on a 401 from anything other than the
/// token-issuing endpoints — the mobile counterpart of the Dashboard's
/// `authInterceptor`. [getAccessToken]/[refreshAccessToken]/[onSessionExpired]
/// are injected rather than this package depending on `auth` directly
/// (`auth` depends on `api_client`, never the reverse) — `mobile/apps/*
/// /lib/src/*_provider.dart` wires the real `TokenStorage`-backed closures
/// in at app start, exactly the constructor-injectable-functions pattern
/// `local_storage`'s `DriftLocalDatabase` already established.
final class ApiClient {
  ApiClient({
    required String baseUrl,
    String? Function()? getAccessToken,
    Future<String?> Function()? refreshAccessToken,
    void Function()? onSessionExpired,
    Future<void> Function()? waitForSession,
  }) : // The public named parameter cannot be a private initializing formal.
       // ignore: prefer_initializing_formals
       _waitForSession = waitForSession,
       _getAccessToken = getAccessToken ?? (() => null),
       _refreshAccessToken = refreshAccessToken ?? (() async => null),
       _onSessionExpired = onSessionExpired ?? (() {}) {
    // Explicit timeouts: Dio has none by default, so a stalled connection
    // would leave a screen's loader spinning forever.
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        sendTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Hold every request that needs a session until the start-up
          // restore has finished, so none is sent with no token and fails.
          // The auth endpoints (the restore itself, sign-in) never wait.
          final gate = _waitForSession;
          if (gate != null && !_isAuthPath(options.path)) await gate();
          final token = _getAccessToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final isAuthEndpoint = _authEndpointPaths.any(
            (path) => error.requestOptions.path.contains(path),
          );
          if (error.response?.statusCode != 401 || isAuthEndpoint) {
            handler.next(error);
            return;
          }

          // `refreshAccessToken` must persist the new token to the same
          // store `getAccessToken` reads from *before* returning it —
          // `dio.fetch()` below re-runs the whole interceptor chain
          // (including `onRequest`), so a `getAccessToken` that still
          // returns the old value would silently overwrite the header set
          // here and retry with the stale token again.
          final newToken = await _refreshAccessToken();
          if (newToken == null) {
            _onSessionExpired();
            handler.next(error);
            return;
          }

          try {
            final retryOptions = error.requestOptions
              ..headers['Authorization'] = 'Bearer $newToken';
            // A `FormData` body is a single-use stream — the original
            // (failed) request already consumed it, so replaying
            // `error.requestOptions` as-is would send an empty body and the
            // server would reject it with a validation error. This bit
            // multipart uploads (`KycApi.uploadAttachment`) specifically:
            // the very first call after a cold start races session-restore,
            // 401s, and then "succeeds" the refresh only to retry with
            // nothing attached. `FormData.clone()` re-materialises it.
            if (retryOptions.data is FormData) {
              retryOptions.data = (retryOptions.data as FormData).clone();
            }
            final response = await dio.fetch<dynamic>(retryOptions);
            handler.resolve(response);
          } on DioException catch (retryError) {
            handler.next(retryError);
          }
        },
      ),
    );
  }

  late final Dio dio;

  final Future<void> Function()? _waitForSession;

  static bool _isAuthPath(String path) => path.contains('/auth/');

  final String? Function() _getAccessToken;
  final Future<String?> Function() _refreshAccessToken;
  final void Function() _onSessionExpired;
}
