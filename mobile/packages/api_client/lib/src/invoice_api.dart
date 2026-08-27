import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's `/invoices/*` routes. Only the
/// two read routes are exposed here — `payments`/`refunds` mutation
/// endpoints on this router are staff-only, not reachable by the
/// `customer` role this app authenticates as.
final class InvoiceApi {
  const InvoiceApi(this._dio);

  final Dio _dio;

  /// Fetch a paginated list of invoices for the current customer. `page` is
  /// 1-indexed, matching the backend's `InvoicePageResponse`.
  Future<Result<InvoicePageResponse>> getMyInvoices({
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/invoices',
        queryParameters: {'page': page, 'page_size': pageSize},
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(InvoicePageResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<InvoiceResponse>> getInvoice(String invoiceId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/invoices/$invoiceId',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(InvoiceResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
