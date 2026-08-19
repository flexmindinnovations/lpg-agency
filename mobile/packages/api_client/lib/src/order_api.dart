import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models.dart';

/// Hand-written wrapper for the backend's `/orders/*` routes.
final class OrderApi {
  const OrderApi(this._dio);

  final Dio _dio;

  /// Fetch a paginated list of orders for the current customer
  Future<Result<OrderPageResponse>> getMyOrders({
    int page = 1,
    int size = 50,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/orders',
        queryParameters: {'page': page, 'size': size},
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(OrderPageResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Fetch details of a specific order
  Future<Result<OrderResponse>> getOrder(String orderId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/orders/$orderId',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(OrderResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
