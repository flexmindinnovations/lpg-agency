import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the load-out weighment check the office logs
/// before a van is loaded (`/scales`, `/routes/{id}/weighment`).
final class WeighmentApi {
  const WeighmentApi(this._dio);

  final Dio _dio;

  /// Scales in service (`GET /scales?status=active`). Needs
  /// `weighment:record`; a role without it gets a failure.
  Future<Result<List<ScaleSummary>>> listActiveScales() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/scales',
        queryParameters: {'status': 'active', 'limit': 200},
      );
      return Success([
        for (final e in response.data?['items'] as List<dynamic>? ?? const [])
          ScaleSummary.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Checks already on file for a trip (`GET /routes/{id}/weighment`).
  Future<Result<List<WeighmentRecord>>> listForRoute(String routeId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/routes/$routeId/weighment',
      );
      return Success([
        for (final e in response.data?['items'] as List<dynamic>? ?? const [])
          WeighmentRecord.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Logs a 100% load-out check for one cylinder type
  /// (`POST /routes/{id}/weighment`): every one of [cylinders] was weighed,
  /// [underweight] of them came up short.
  Future<Result<WeighmentRecord>> recordLoadOut(
    String routeId, {
    required String scaleId,
    required String cylinderTypeId,
    required int cylinders,
    required int underweight,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/routes/$routeId/weighment',
        data: {
          'scale_id': scaleId,
          'cylinder_type_id': cylinderTypeId,
          'total_cylinders_in_batch': cylinders,
          'cylinders_checked': cylinders,
          'underweight_cylinder_count': underweight,
        },
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(WeighmentRecord.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Logs the sample weighed when a truck was received
  /// (`POST /goods-receipt-notes/{id}/weighment`): [checked] of the
  /// [batch] were weighed and [underweight] came up short. It never blocks
  /// the receipt itself.
  Future<Result<WeighmentRecord>> recordReceiptSample(
    String goodsReceiptId, {
    required String scaleId,
    required String cylinderTypeId,
    required int batch,
    required int checked,
    required int underweight,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/goods-receipt-notes/$goodsReceiptId/weighment',
        data: {
          'scale_id': scaleId,
          'cylinder_type_id': cylinderTypeId,
          'total_cylinders_in_batch': batch,
          'cylinders_checked': checked,
          'underweight_cylinder_count': underweight,
        },
      );
      return Success(WeighmentRecord.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
