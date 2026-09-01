import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the Driver App's slice of the backend's
/// `/routes/*` routes.
final class RouteApi {
  const RouteApi(this._dio);

  final Dio _dio;

  /// The calling driver's active route, resolved from the auth token.
  /// `Success(null)` when the driver has no active route (the backend
  /// answers `404`).
  Future<Result<RouteSummary?>> getMyActiveRoute() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/routes/active',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteSummary.fromJson(response.data!));
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        return const Success(null);
      }
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Report the driver's current position. Only accepted while the route is
  /// `in_progress` (else the backend answers `409`).
  Future<Result<void>> reportLocation(
    String routeId,
    DriverLocationReport report,
  ) async {
    try {
      await _dio.post<void>(
        '/api/v1/routes/$routeId/location',
        data: report.toJson(),
      );
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
