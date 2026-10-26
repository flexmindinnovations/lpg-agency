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
        queryParameters: {'skip': (page - 1) * size, 'limit': size},
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

  /// `booked -> confirmed` (staff).
  Future<Result<OrderResponse>> confirmOrder(String orderId) =>
      _postOrderAction('/api/v1/orders/$orderId/confirm');

  /// `failed_delivery -> confirmed` on a new [requestedDate]: the order
  /// leaves its trip and waits to be sent out again.
  Future<Result<OrderResponse>> rescheduleOrder(
    String orderId,
    DateTime requestedDate,
  ) => _postOrderAction(
    '/api/v1/orders/$orderId/reschedule',
    data: {'requested_date': requestedDate.toUtc().toIso8601String()},
  );

  /// `delivered -> closed`.
  Future<Result<OrderResponse>> closeOrder(String orderId) =>
      _postOrderAction('/api/v1/orders/$orderId/close');

  /// Approves the waiting post-dispatch cancellation request (Manager).
  Future<Result<OrderResponse>> approveCancellation(String orderId) =>
      _postOrderAction('/api/v1/orders/$orderId/cancel/approve');

  /// Rejects the waiting cancellation request; the order carries on and the
  /// requester sees [reason].
  Future<Result<void>> rejectCancellation(String orderId, String reason) async {
    try {
      await _dio.post<dynamic>(
        '/api/v1/orders/$orderId/cancel/reject',
        data: {'reason': reason},
      );
      return const Success(null);
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

  /// Sends the customer a fresh delivery OTP for an `out_for_delivery` order,
  /// replacing the earlier one (lost, never arrived, or expired). A `409`
  /// means the order is no longer out for delivery; a `503` means the SMS
  /// could not be sent.
  Future<Result<void>> resendDeliveryOtp(String orderId) async {
    try {
      await _dio.post<void>('/api/v1/orders/$orderId/delivery-otp');
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// **Testing only.** The delivery OTP last sent for this order, from the
  /// backend's dev inbox (`GET /dev/orders/{id}/delivery-otp`). That route
  /// does not exist in production, so callers must treat a failure as "no
  /// code to show".
  Future<Result<String>> fetchDevDeliveryOtp(String orderId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/dev/orders/$orderId/delivery-otp',
      );
      return Success(response.data!['code'] as String);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

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
  /// [note] is the driver's free text ("gate locked, back at 6"), shown with
  /// the reason in the order's history.
  Future<Result<OrderResponse>> recordFailedDelivery(
    String orderId, {
    required String reasonCode,
    String? resolutionAction,
    String? note,
  }) => _postOrderAction(
    '/api/v1/orders/$orderId/failed-delivery',
    data: {
      'reason_code': reasonCode,
      'resolution_action': ?resolutionAction,
      'note': ?note,
    },
  );

  /// The delivery code the customer gives the driver, for the signed-in
  /// customer's own order while it is out for delivery. `null` when no code
  /// is pending.
  Future<Result<String?>> getDeliveryCode(String orderId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>?>(
        '/api/v1/orders/$orderId/delivery-code',
      );
      return Success(response.data?['code'] as String?);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// The cancellation request waiting for a manager on this order, or
  /// `null` when there is none.
  Future<Result<PendingCancellationResponse?>> getPendingCancellation(
    String orderId,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>?>(
        '/api/v1/orders/$orderId/cancellation-request',
      );
      final data = response.data;
      return Success(
        data == null ? null : PendingCancellationResponse.fromJson(data),
      );
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// The order's status history, oldest first.
  Future<Result<List<OrderStatusHistoryEntry>>> getStatusHistory(
    String orderId,
  ) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/orders/$orderId/history',
      );
      return Success([
        for (final e in response.data ?? const [])
          OrderStatusHistoryEntry.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

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
