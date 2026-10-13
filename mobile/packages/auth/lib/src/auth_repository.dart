// The constructor keeps clean public parameter names (`authApi`,
// `tokenStorage`) while the backing fields stay private (`_authApi`,
// `_tokenStorage`) — an initializing formal would force the parameter name
// to match the private field name too, which isn't a better public API.
// ignore_for_file: prefer_initializing_formals

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';

import 'token_storage.dart';

/// Business logic for authentication — orchestrates [AuthApi] calls and
/// [TokenStorage] persistence, framework-agnostic (no Riverpod, no widgets)
/// so it can be unit-tested in isolation and reused by either app.
abstract interface class AuthRepository {
  /// The current in-memory access token, or `null` if there is no session.
  ///
  /// Read synchronously by `ApiClient`'s `getAccessToken` callback at every
  /// request — this is why it lives in memory, not behind an async storage
  /// read.
  String? get accessToken;

  Future<Result<Principal>> login({
    required String email,
    required String password,
  });

  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  });

  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  });

  /// Redeems whatever refresh token [TokenStorage] holds for a fresh access
  /// token + principal. Called both once at app startup (silent session
  /// restore) and by `ApiClient`'s 401 handler.
  Future<Result<Principal>> restoreSession();

  Future<Result<void>> requestPasswordReset({required String email});

  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  });

  Future<void> logout();
}

final class ApiAuthRepository implements AuthRepository {
  ApiAuthRepository({
    required AuthApi authApi,
    required TokenStorage tokenStorage,
  }) : _authApi = authApi,
       _tokenStorage = tokenStorage;

  final AuthApi _authApi;
  final TokenStorage _tokenStorage;
  String? _accessToken;

  @override
  String? get accessToken => _accessToken;

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async {
    final tokenResult = await _authApi.login(email: email, password: password);
    return _hydrateFrom(tokenResult);
  }

  @override
  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) => _authApi.requestOtp(tenantId: tenantId, phoneNumber: phoneNumber);

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async {
    final tokenResult = await _authApi.verifyOtp(
      tenantId: tenantId,
      phoneNumber: phoneNumber,
      code: code,
    );
    return _hydrateFrom(tokenResult);
  }

  @override
  Future<Result<Principal>> restoreSession() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken == null) {
      return const FailureResult(
        Failure(message: 'No session to restore.', errorCode: 'NO_SESSION'),
      );
    }
    final tokenResult = await _authApi.refresh(refreshToken: refreshToken);
    return _hydrateFrom(tokenResult);
  }

  @override
  Future<Result<void>> requestPasswordReset({required String email}) =>
      _authApi.requestPasswordReset(email: email);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) => _authApi.confirmPasswordReset(
    resetToken: resetToken,
    newPassword: newPassword,
  );

  @override
  Future<void> logout() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken != null) {
      // Best-effort: logout is idempotent server-side (backend's
      // `LogoutUseCase` docstring) and the local session must end either
      // way, so a transport failure here is not surfaced upstream.
      await _authApi.logout(refreshToken: refreshToken);
    }
    _accessToken = null;
    await _tokenStorage.clear();
  }

  Future<Result<Principal>> _hydrateFrom(Result<TokenPair> tokenResult) async {
    return switch (tokenResult) {
      Success(:final value) => await _applyTokens(value),
      FailureResult(:final failure) => FailureResult(failure),
    };
  }

  Future<Result<Principal>> _applyTokens(TokenPair pair) async {
    _accessToken = pair.accessToken;
    await _tokenStorage.saveTokens(
      accessToken: pair.accessToken,
      refreshToken: pair.refreshToken,
    );
    return _authApi.me();
  }
}
