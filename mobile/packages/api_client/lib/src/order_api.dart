import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

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

  /// Fetch the order-tracking view: delivery destination, route status, and
  /// the driver's last-known position (`driverLocation` null until sharing
  /// starts). Live movement arrives separately over `/ws`
  /// (`RealtimeClient.subscribeToDriverLocation`).
  Future<Result<OrderTrackingResponse>> getOrderTracking(String orderId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/tracking',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(OrderTrackingResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Create (book) a new order. The backend requires an `Idempotency-Key`
  /// header on this route — a fresh v4 UUID is generated per call, so a
  /// caller that retries after a network failure should reuse the same
  /// [idempotencyKey] rather than calling this again, or the retry will be
  /// treated as a genuinely new order.
  Future<Result<OrderResponse>> createOrder(
    CreateOrderRequest request, {
    String? idempotencyKey,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders',
        data: request.toJson(),
        options: Options(
          headers: {'Idempotency-Key': idempotencyKey ?? const Uuid().v4()},
        ),
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

  /// `ready_for_dispatch -> out_for_delivery` — the driver departs with the
  /// vehicle. The backend issues the delivery OTP to the customer.
  Future<Result<OrderResponse>> departOrder(String orderId) =>
      _postOrderAction('/api/v1/orders/$orderId/depart');

  /// Pre-upload a signature/photo blob for a proof of delivery. Returns the
  /// `blob_ref` to pass into [deliverOrder].
  Future<Result<PodAttachmentResponse>> uploadPodAttachment(
    String orderId, {
    required List<int> bytes,
    required String filename,
    String contentType = 'image/png',
  }) async {
    try {
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          bytes,
          filename: filename,
          contentType: DioMediaType.parse(contentType),
        ),
      });
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/pod-attachments',
        data: form,
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(PodAttachmentResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// `out_for_delivery -> delivered`. Idempotency-Key required (a fresh v4
  /// UUID per call; a retry after a network failure should reuse the same
  /// [idempotencyKey]). A wrong/expired OTP is a `409`; incomplete proof of
  /// delivery is a `400`.
  Future<Result<DeliverOrderResponse>> deliverOrder(
    String orderId,
    DeliverOrderRequest request, {
    String? idempotencyKey,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/deliver',
        data: request.toJson(),
        options: Options(
          headers: {'Idempotency-Key': idempotencyKey ?? const Uuid().v4()},
        ),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(DeliverOrderResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// `out_for_delivery -> failed_delivery`. `reasonCode` is one of
  /// `customer_unavailable` / `wrong_address` / `payment_refused` /
  /// `vehicle_issue` / `safety_issue`; `resolutionAction` is optional
  /// (`reschedule` / `cancel` / `return_stock`).
  Future<Result<OrderResponse>> recordFailedDelivery(
    String orderId, {
    required String reasonCode,
    String? resolutionAction,
  }) => _postOrderAction(
    '/api/v1/orders/$orderId/failed-delivery',
    data: {'reason_code': reasonCode, 'resolution_action': ?resolutionAction},
  );

  Future<Result<OrderResponse>> _postOrderAction(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(path, data: data);
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

  /// Cancel an order. Returns [CancelOrderResponse.pendingApproval] `true`
  /// when the order had already been dispatched — the order itself stays in
  /// its current status pending Manager approval (D-19), rather than moving
  /// straight to `cancelled`.
  Future<Result<CancelOrderResponse>> cancelOrder(
    String orderId,
    String reason,
  ) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/cancel',
        data: CancelOrderRequest(reason: reason).toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(CancelOrderResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
