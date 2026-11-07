import 'package:core/core.dart';
import 'package:dio/dio.dart';

/// What the server says about this phone (`GET /devices/me`).
class DeviceStatusReport {
  const DeviceStatusReport({
    required this.control,
    required this.status,
    required this.allowed,
    this.displayName,
    this.needsName = false,
  });

  factory DeviceStatusReport.fromJson(Map<String, dynamic> json) =>
      DeviceStatusReport(
        control: json['control'] as String? ?? 'off',
        status: json['status'] as String?,
        allowed: json['allowed'] as bool? ?? true,
        displayName: json['display_name'] as String?,
        needsName: json['needs_name'] as bool? ?? false,
      );

  /// The agency's mode: `off`, `observe` or `enforce`.
  final String control;

  /// `pending`, `approved`, `blocked` or `removed`; `null` when the session
  /// is not under device control.
  final String? status;

  /// Whether the agency lets this phone use the app right now.
  final bool allowed;
  final String? displayName;

  /// True when the agency has not seen this phone before and nobody has named
  /// it: the app asks for a name once. False for a phone already registered.
  final bool needsName;
}

/// `GET /api/v1/devices/me` — the one call a waiting or blocked phone can
/// still make. Returns a [Result] like the rest of `api_client`'s wrappers.
class DeviceApi {
  const DeviceApi(this._dio);

  final Dio _dio;

  Future<Result<DeviceStatusReport>> me() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/devices/me',
      );
      return Success(DeviceStatusReport.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(_failureFrom(error));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// `PUT /api/v1/devices/me/name` — names this phone. The server refuses a
  /// name another phone in the agency already has (`DUPLICATE_DEVICE_NAME`)
  /// and says which name to try instead in the message.
  Future<Result<DeviceStatusReport>> setName(String name) async {
    try {
      final response = await _dio.put<Map<String, dynamic>>(
        '/api/v1/devices/me/name',
        data: {'name': name},
      );
      return Success(DeviceStatusReport.fromJson(response.data!));
    } on DioException catch (error) {
      return FailureResult(_failureFrom(error));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}

/// Just enough of `api_client`'s failure mapping for this one call: the
/// server's `error_code` (what the access controller branches on) and a
/// message. A network failure carries no code, so it changes nothing.
Failure _failureFrom(DioException error) {
  final data = error.response?.data;
  if (data is Map<String, dynamic> && data['error_code'] is String) {
    final detail = data['detail'];
    return Failure(
      message: detail is String && detail.isNotEmpty
          ? detail
          : 'Could not check this phone.',
      errorCode: data['error_code'] as String,
    );
  }
  return const Failure(message: 'Could not check this phone.');
}
