import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's online-payment routes (ADR-053).
///
/// Payment happens on Razorpay's hosted page: [createPaymentLink] returns
/// its URL, the app opens it, and [refreshPayment] asks the backend to
/// re-check the outcome when the customer comes back.
final class PaymentApi {
  const PaymentApi(this._dio);

  final Dio _dio;

  /// Create (or reuse the still-open) payment link for what is owed on
  /// [orderId].
  Future<Result<OnlinePaymentResponse>> createPaymentLink(String orderId) =>
      _single(() => _dio.post('/api/v1/orders/$orderId/payment-links'));

  /// Whether online payment can be offered at all (a gateway is
  /// configured). When it isn't, creating a link fails with 503.
  Future<Result<bool>> isAvailable() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/online-payments/availability',
      );
      return Success(response.data?['available'] == true);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Every payment attempt for [orderId], newest first.
  Future<Result<List<OnlinePaymentResponse>>> listOrderPayments(
    String orderId,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/online-payments',
      );
      final items = (response.data?['items'] as List<dynamic>? ?? const [])
          .map((e) => OnlinePaymentResponse.fromJson(e as Map<String, dynamic>))
          .toList();
      return Success(items);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Ask the backend to re-check [onlinePaymentId] with the gateway.
  Future<Result<OnlinePaymentResponse>> refreshPayment(
    String onlinePaymentId,
  ) => _single(
    () => _dio.post('/api/v1/online-payments/$onlinePaymentId/refresh'),
  );

  /// The agency's bank and UPI details (`GET /payment-profile`).
  Future<Result<PaymentProfile>> getPaymentProfile() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/payment-profile',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(PaymentProfile.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Replace the agency's bank and UPI details (`PUT /payment-profile`,
  /// needs `tenant:configure`). The server validates IFSC, account number
  /// and UPI ID and answers 422 with a readable message.
  Future<Result<PaymentProfile>> savePaymentProfile(
    PaymentProfile profile,
  ) async {
    try {
      final response = await _dio.put<Map<String, dynamic>>(
        '/api/v1/payment-profile',
        data: profile.toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(PaymentProfile.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// UPI link and QR for what is still owed on an order or invoice. `409`
  /// when the agency has no UPI ID or nothing is due.
  Future<Result<UpiQr>> getUpiQr({String? orderId, String? invoiceId}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/payments/upi-qr',
        queryParameters: {'order_id': ?orderId, 'invoice_id': ?invoiceId},
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(UpiQr.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<OnlinePaymentResponse>> _single(
    Future<Response<Map<String, dynamic>>> Function() request,
  ) async {
    try {
      final response = await request();
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(OnlinePaymentResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
