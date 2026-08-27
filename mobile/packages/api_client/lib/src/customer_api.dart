import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's `/customers/*` routes.
final class CustomerApi {
  const CustomerApi(this._dio);

  final Dio _dio;

  Future<Result<CustomerResponse>> getMyProfile() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/customers/me',
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
      // Deliberately not `_dio.post<String>` — dio special-cases a `String`
      // type parameter to `ResponseType.plain`, which skips JSON decoding
      // entirely. The backend returns a bare JSON string (`"<uuid>"`), so a
      // plain-text read would hand back the id with its surrounding quote
      // characters still attached.
      final response = await _dio.post<dynamic>(
        '/api/v1/customers/$customerId/addresses',
        data: request.toJson(),
      );
      final id = response.data;
      if (id is! String) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(id);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<void>> updateAddress(
    String customerId,
    String addressId,
    UpdateCustomerAddressRequest request,
  ) async {
    try {
      await _dio.put<void>(
        '/api/v1/customers/$customerId/addresses/$addressId',
        data: request.toJson(),
      );
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<void>> setPrimaryAddress(
    String customerId,
    String addressId,
  ) async {
    try {
      await _dio.put<void>(
        '/api/v1/customers/$customerId/addresses/$addressId/primary',
      );
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
