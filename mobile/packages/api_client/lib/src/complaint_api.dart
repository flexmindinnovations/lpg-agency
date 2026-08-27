import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's `/complaints/*` routes. `assign`/
/// `resolve` are staff-only in practice (a `customer` principal's own
/// complaints are always `Open` from their side) and are not exposed here.
final class ComplaintApi {
  const ComplaintApi(this._dio);

  final Dio _dio;

  /// Fetch a paginated list of complaints for the current customer.
  /// `skip`/`limit` are offset-based, matching the backend's
  /// `ComplaintListResponse` — a different pagination shape than
  /// [InvoiceApi.getMyInvoices]'s `page`/`pageSize`.
  Future<Result<ComplaintListResponse>> getMyComplaints({
    int skip = 0,
    int limit = 50,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/complaints',
        queryParameters: {'skip': skip, 'limit': limit},
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(ComplaintListResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<ComplaintResponse>> getComplaint(String complaintId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/complaints/$complaintId',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(ComplaintResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Raise a new complaint. Returns the new complaint's id — the backend
  /// responds with a bare `{"id": ...}`, not a full [ComplaintResponse];
  /// follow up with [getComplaint] if the full record is needed.
  Future<Result<String>> raiseComplaint(RaiseComplaintRequest request) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/complaints',
        data: request.toJson(),
      );
      final id = response.data?['id'] as String?;
      if (id == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(id);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
