import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's cylinder-type catalog endpoint.
///
/// Lives under `/admin/cylinder-types` in the backend router, but
/// `list_cylinder_types` is gated only by authentication
/// (`get_current_principal`, no `require_permission` call) — every role
/// including `customer` can read it, since it's the tenant's product
/// catalog, not an admin-only resource. The path is misleading; the
/// permission model is not.
final class CylinderTypeApi {
  const CylinderTypeApi(this._dio);

  final Dio _dio;

  Future<Result<List<CylinderTypeResponse>>> list() async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/admin/cylinder-types',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(
        response.data!
            .map(
              (e) => CylinderTypeResponse.fromJson(e as Map<String, dynamic>),
            )
            .toList(),
      );
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
