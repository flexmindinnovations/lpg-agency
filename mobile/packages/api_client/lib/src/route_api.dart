import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

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

  /// The calling driver's routes, newest first, already scoped server-side to
  /// their own (`GET /routes`). Used for the delivery-history list; pass a
  /// `status` to narrow it (e.g. `completed`).
  Future<Result<List<RouteSummary>>> listRoutes({
    String? status,
    String? branchId,
    int pageSize = 20,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/routes',
        queryParameters: {
          'page_size': pageSize,
          'status': ?status,
          'branch_id': ?branchId,
        },
      );
      final items = (response.data?['items'] as List<dynamic>? ?? const [])
          .map((e) => RouteSummary.fromJson(e as Map<String, dynamic>))
          .toList();
      return Success(items);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// The driver confirms the van matches the load manifest
  /// (`POST /routes/{id}/confirm-load`). Soft — the backend does *not* gate
  /// departing on it. An `Idempotency-Key` is sent so a queued offline retry
  /// replays rather than re-confirming; a fresh v4 unless [idempotencyKey] is
  /// passed. `409` if the route isn't `loaded`.
  Future<Result<RouteSummary>> confirmLoad(
    String routeId, {
    String? idempotencyKey,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/routes/$routeId/confirm-load',
        options: Options(
          headers: {'Idempotency-Key': idempotencyKey ?? const Uuid().v4()},
        ),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteSummary.fromJson(response.data!));
    } on DioException catch (e) {
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

  /// Plans a new (empty) trip for a driver and van (`POST /routes`).
  Future<Result<RouteSummary>> planRoute({
    required String branchId,
    required String driverId,
    required String vehicleId,
    DateTime? routeDate,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/routes',
        data: {
          'branch_id': branchId,
          'driver_id': driverId,
          'vehicle_id': vehicleId,
          'route_date': ?routeDate?.toUtc().toIso8601String(),
        },
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteSummary.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Cancels a trip that hasn't left yet (`PATCH /routes/{id}/status`,
  /// planned or loaded only).
  Future<Result<RouteSummary>> cancelRoute(String routeId) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/api/v1/routes/$routeId/status',
        data: {'status': 'cancelled'},
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteSummary.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// The trip sheet's one action (`POST /routes/{id}/load-and-dispatch`):
  /// adds [orderIds], moves what they need from [warehouseId] onto the van
  /// and releases the trip to the driver. `409 INSUFFICIENT_STOCK` when the
  /// godown is short.
  Future<Result<RouteSummary>> loadAndDispatch(
    String routeId, {
    required String warehouseId,
    List<String> orderIds = const [],
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/routes/$routeId/load-and-dispatch',
        data: {
          'warehouse_id': warehouseId,
          'order_ids': orderIds,
          'extra_lines': <Map<String, dynamic>>[],
        },
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteSummary.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
