import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the Driver App's slice of the backend's
/// `/cash-handovers/*` routes — the end-of-route cash reconciliation.
final class CashHandoverApi {
  const CashHandoverApi(this._dio);

  final Dio _dio;

  /// What the driver owes for a completed route (`expected_amount`, computed
  /// server-side from real cash proof-of-delivery records) plus the declared
  /// handover once it exists. `404` if the route isn't the caller's.
  Future<Result<RouteCashHandover>> getForRoute(String routeId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/cash-handovers/for-route/$routeId',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RouteCashHandover.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Declare the cash handed over for a route. `actualAmount` is sent as a
  /// fixed-2 string so it round-trips the backend's `Decimal` without float
  /// drift. `409 CONFLICT` if a handover was already declared for the route;
  /// `422` if the route isn't `completed` yet.
  Future<Result<CashHandover>> declare({
    required String routeId,
    required String driverId,
    required double actualAmount,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/cash-handovers',
        data: {
          'driver_id': driverId,
          'route_id': routeId,
          'actual_amount': actualAmount.toStringAsFixed(2),
        },
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(CashHandover.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
