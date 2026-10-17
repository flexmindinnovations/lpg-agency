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
