import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the price list (`/admin/price-list`): what each
/// cylinder type costs each kind of customer, and the oil companies' rate
/// changes waiting to be reviewed. Changing prices needs `tenant:configure`.
final class PriceListApi {
  const PriceListApi(this._dio);

  final Dio _dio;

  /// Every price ever set (`GET /admin/price-list`), history included.
  Future<Result<List<PriceEntry>>> listPrices() => _guard(() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/admin/price-list');
    return [
      for (final e in response.data ?? const [])
        PriceEntry.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Sets a price (`POST /admin/price-list`), from [effectiveFrom] or now.
  /// It does not edit the old entry; it adds a newer one, so history stays.
  /// [branchId] `null` sets the agency-wide default.
  Future<Result<PriceEntry>> setPrice({
    required String cylinderTypeId,
    required String customerType,
    required double price,
    String? branchId,
    DateTime? effectiveFrom,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/price-list',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'customer_type': customerType,
        // A string keeps the paise exact; the server reads it as a decimal.
        'price': price.toStringAsFixed(2),
        'branch_id': ?branchId,
        'effective_from': ?effectiveFrom?.toUtc().toIso8601String(),
      },
    );
    return PriceEntry.fromJson(response.data!);
  });

  /// Rate changes still waiting for review
  /// (`GET /admin/price-list/proposals`).
  Future<Result<List<PriceProposal>>> listProposals() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/admin/price-list/proposals',
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        PriceProposal.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Accepts (it becomes a price) or rejects a proposal
  /// (`PATCH /admin/price-list/proposals/{id}`).
  Future<Result<void>> reviewProposal(String id, {required bool accept}) =>
      _guard(() async {
        await _dio.patch<Map<String, dynamic>>(
          '/api/v1/admin/price-list/proposals/$id',
          data: {'action': accept ? 'accept' : 'reject'},
        );
      });

  Future<Result<T>> _guard<T>(Future<T> Function() call) async {
    try {
      return Success(await call());
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
