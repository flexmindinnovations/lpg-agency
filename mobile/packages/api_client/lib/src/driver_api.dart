import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the Driver App's slice of the backend's
/// `/drivers/*` routes.
final class DriverApi {
  const DriverApi(this._dio);

  final Dio _dio;

  /// The calling driver's own profile, resolved from the auth token
  /// (`GET /drivers/me`). `404` if the caller isn't a driver.
  Future<Result<DriverMe>> getMe() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/drivers/me',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(DriverMe.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
