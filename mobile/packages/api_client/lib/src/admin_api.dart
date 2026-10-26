import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for administrative, executive dashboard, and approval operations.
final class AdminApi {
  const AdminApi(this._dio);

  final Dio _dio;

  /// The caller's agency (`GET /api/v1/admin/tenant`, needs `tenant:read`).
  Future<Result<AgencyTenantResponse>> getTenant() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/admin/tenant',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(AgencyTenantResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Executive dashboard summary (`GET /api/v1/dashboard/summary`)
  Future<Result<DashboardSummaryResponse>> getDashboardSummary() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/dashboard/summary',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(DashboardSummaryResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Operations snapshot KPIs (`GET /api/v1/dashboard/operations`)
  Future<Result<OperationsSnapshotResponse>> getOperationsSnapshot() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/dashboard/operations',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(OperationsSnapshotResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// List driver cash handovers (`GET /api/v1/cash-handovers`)
  Future<Result<List<CashHandoverRegisterEntryResponse>>> listCashHandovers({
    String? reviewStatus,
  }) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/cash-handovers',
        queryParameters: {'review_status': ?reviewStatus},
      );
      final list = (response.data ?? [])
          .map(
            (e) => CashHandoverRegisterEntryResponse.fromJson(
              e as Map<String, dynamic>,
            ),
          )
          .toList();
      return Success(list);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Review driver cash handover (`POST /api/v1/cash-handovers/{id}/review`)
  Future<Result<CashHandoverReviewResponse>> reviewCashHandover(
    String cashHandoverId,
    ReviewCashHandoverRequest request,
  ) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/cash-handovers/$cashHandoverId/review',
        data: request.toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(CashHandoverReviewResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Approve or reject customer KYC document (`POST /api/v1/customers/{customerId}/kyc/{docId}/verify`)
  Future<Result<void>> verifyKycDocument(
    String customerId,
    String docId,
    VerifyKycDocumentRequest request,
  ) async {
    try {
      await _dio.post<dynamic>(
        '/api/v1/customers/$customerId/kyc/$docId/verify',
        data: request.toJson(),
      );
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
