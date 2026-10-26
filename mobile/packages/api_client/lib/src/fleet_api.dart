import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'models/models.dart';
import 'failure_mapper.dart';

/// Hand-written wrapper for what the office needs to send an order out:
/// drivers, vans, godowns and the filled stock at a godown or on a van.
final class FleetApi {
  const FleetApi(this._dio);

  final Dio _dio;

  /// Every driver (`GET /drivers`), one page of up to [limit].
  Future<Result<List<FleetDriver>>> listDrivers({int limit = 200}) =>
      _list('/api/v1/drivers', limit, FleetDriver.fromJson);

  /// Every van (`GET /vehicles`), one page of up to [limit].
  Future<Result<List<FleetVehicle>>> listVehicles({int limit = 200}) =>
      _list('/api/v1/vehicles', limit, FleetVehicle.fromJson);

  /// Every godown (`GET /admin/warehouses`).
  Future<Result<List<FleetWarehouse>>> listWarehouses() async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/admin/warehouses',
      );
      return Success([
        for (final e in response.data ?? const [])
          FleetWarehouse.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Filled cylinders at a `warehouse` or `vehicle`, summed per cylinder
  /// type id (`GET /inventory-locations/{type}/{id}/balance`).
  Future<Result<Map<String, int>>> getFilledStock(
    String locationType,
    String locationId,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/inventory-locations/$locationType/$locationId/balance',
      );
      final stock = <String, int>{};
      for (final line in response.data?['balances'] as List<dynamic>? ?? []) {
        final map = line as Map<String, dynamic>;
        if (map['status'] != 'filled') continue;
        final id = map['cylinder_type_id'] as String;
        stock[id] = (stock[id] ?? 0) + (map['quantity'] as num).toInt();
      }
      return Success(stock);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<List<T>>> _list<T>(
    String path,
    int limit,
    T Function(Map<String, dynamic>) parse,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: {'skip': 0, 'limit': limit},
      );
      return Success([
        for (final e in response.data?['items'] as List<dynamic>? ?? const [])
          parse(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
