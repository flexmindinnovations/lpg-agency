import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models.dart';

/// Hand-written wrapper for the backend's `/auth/*` routes (ADR-037) —
/// spec-generation isn't justified yet for ~8 endpoints. Every method
/// returns [Result] instead of throwing, so a caller cannot forget to
/// handle a failure (`core`'s own `Result` docstring).
final class AuthApi {
  const AuthApi(this._dio);

  final Dio _dio;

  Future<Result<TokenPair>> login({
    required String email,
    required String password,
  }) => _postForTokens('/api/v1/auth/login', {
    'email': email,
    'password': password,
  });

  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) => _post('/api/v1/auth/otp/request', {
    'tenant_id': tenantId,
    'phone_number': phoneNumber,
  });

  Future<Result<TokenPair>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) => _postForTokens('/api/v1/auth/otp/verify', {
    'tenant_id': tenantId,
    'phone_number': phoneNumber,
    'code': code,
  });

  /// `refreshToken` mirrors `RefreshRequest`'s own docstring: mobile clients
  /// have no cookie, so they always supply it explicitly.
  Future<Result<TokenPair>> refresh({required String refreshToken}) =>
      _postForTokens('/api/v1/auth/refresh', {'refresh_token': refreshToken});

  Future<Result<void>> logout({required String refreshToken}) =>
      _post('/api/v1/auth/logout', {'refresh_token': refreshToken});

  Future<Result<Principal>> me() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/api/v1/auth/me');
      return Success(Principal.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }

  Future<Result<void>> requestPasswordReset({required String email}) =>
      _post('/api/v1/auth/password/forgot', {'email': email});

  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) => _post('/api/v1/auth/password/reset', {
    'reset_token': resetToken,
    'new_password': newPassword,
  });

  Future<Result<TokenPair>> _postForTokens(
    String path,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(path, data: data);
      return Success(TokenPair.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }

  Future<Result<void>> _post(String path, Map<String, dynamic> data) async {
    try {
      await _dio.post<void>(path, data: data);
      return const Success(null);
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }
}
