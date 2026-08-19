import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models.dart';

/// Hand-written wrapper for the backend's `/customers/*` routes.
final class CustomerApi {
  const CustomerApi(this._dio);

  final Dio _dio;

  Future<Result<CustomerResponse>> getCustomer(String customerId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/customers/$customerId',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(CustomerResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<CustomerResponse>> updateCustomer(
    String customerId,
    UpdateCustomerProfileRequest request,
  ) async {
    try {
      final response = await _dio.put<Map<String, dynamic>>(
        '/api/v1/customers/$customerId',
        data: request.toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(CustomerResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<String>> addCustomerAddress(
    String customerId,
    AddCustomerAddressRequest request,
  ) async {
    try {
      final response = await _dio.post<String>(
        '/api/v1/customers/$customerId/addresses',
        data: request.toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(response.data!);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
