import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

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

  /// Reads back the OTP the backend just "sent" from its dev inbox
  /// (`GET /dev/otp-inbox/{phone}`). That route exists only when the backend
  /// is not running in production, so this fails (404) everywhere real SMS
  /// delivery is in use — callers must treat a failure as "no code to show".
  Future<Result<String>> fetchDevOtp({required String phoneNumber}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/dev/otp-inbox/${Uri.encodeComponent(phoneNumber)}',
      );
      return Success(response.data!['code'] as String);
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

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

  /// The signed-in staff member's own name and contact number.
  Future<Result<MyProfile>> myProfile() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/auth/me/profile',
      );
      return Success(MyProfile.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }

  /// Sets the signed-in staff member's own name and contact number. The
  /// server replaces both, so send the one you are not changing as it is; an
  /// empty string clears a value.
  Future<Result<MyProfile>> updateMyProfile({
    required String displayName,
    required String contactPhone,
  }) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/api/v1/auth/me/profile',
        data: {'display_name': displayName, 'contact_phone': contactPhone},
      );
      return Success(MyProfile.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }

  /// Sets the signed-in staff member's own profile picture, replacing the
  /// old one. The server takes a JPEG, PNG, WebP or HEIC picture of at most
  /// 5 MB and checks the bytes match [contentType].
  Future<Result<MyProfile>> setMyAvatar({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/me/avatar',
        data: FormData.fromMap({
          'file': MultipartFile.fromBytes(
            bytes,
            filename: filename,
            contentType: MediaType.parse(contentType),
          ),
        }),
      );
      return Success(MyProfile.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    }
  }

  /// Removes the signed-in staff member's own profile picture.
  Future<Result<MyProfile>> removeMyAvatar() async {
    try {
      final response = await _dio.delete<Map<String, dynamic>>(
        '/api/v1/auth/me/avatar',
      );
      return Success(MyProfile.fromJson(response.data!));
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
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<void>> _post(String path, Map<String, dynamic> data) async {
    try {
      await _dio.post<void>(path, data: data);
      return const Success(null);
    } on DioException catch (error) {
      return FailureResult(mapDioError(error));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
