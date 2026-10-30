import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's `/complaints/*` routes. A customer
/// sees only their own; staff see the agency's and can assign and resolve.
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
    String? status,
    String? customerId,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/complaints',
        queryParameters: {
          'skip': skip,
          'limit': limit,
          'status': ?status,
          'customer_id': ?customerId,
        },
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

  /// The emergency helpline and the agency's phone, for the Support screen.
  Future<Result<SupportContacts>> getSupportContacts() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/support/contacts',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(SupportContacts.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Active staff a complaint can be assigned to (staff only).
  Future<Result<List<ComplaintAssignee>>> getAssignees() async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/complaints/assignees',
      );
      return Success([
        for (final item in response.data ?? const <dynamic>[])
          ComplaintAssignee.fromJson(item as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Assigns the complaint to [assignedTo], one of [getAssignees]; a resolved
  /// complaint refuses (409).
  Future<Result<void>> assign(String complaintId, String assignedTo) => _post(
    '/api/v1/complaints/$complaintId/assign',
    {'assigned_to': assignedTo},
  );

  /// Resolves the complaint. [outcome] is `Resolved`, `Compensated` or
  /// `Rejected`; [notes] say what was done.
  Future<Result<void>> resolve(
    String complaintId, {
    required String outcome,
    required String notes,
  }) => _post('/api/v1/complaints/$complaintId/resolve', {
    'outcome': outcome,
    'resolution_notes': notes,
  });

  Future<Result<void>> _post(String path, Map<String, dynamic> body) async {
    try {
      await _dio.post<void>(path, data: body);
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
