import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

import 'models/models.dart';
import 'failure_mapper.dart';

/// Hand-written wrapper for what the office needs to send an order out:
/// drivers, vans, godowns and the filled stock at a godown or on a van.
final class FleetApi {
  const FleetApi(this._dio);

  final Dio _dio;

  /// Every driver (`GET /drivers`), one page of up to [limit].
  Future<Result<List<FleetDriver>>> listDrivers({int limit = 200}) =>
      _list('/api/v1/drivers', limit, FleetDriver.fromJson);

  /// Every van (`GET /vehicles`), one page of up to [limit].
  Future<Result<List<FleetVehicle>>> listVehicles({int limit = 200}) =>
      _list('/api/v1/vehicles', limit, FleetVehicle.fromJson);

  /// Every godown (`GET /admin/warehouses`).
  Future<Result<List<FleetWarehouse>>> listWarehouses() async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/api/v1/admin/warehouses',
      );
      return Success([
        for (final e in response.data ?? const [])
          FleetWarehouse.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Filled cylinders at a `warehouse` or `vehicle`, summed per cylinder
  /// type id (`GET /inventory-locations/{type}/{id}/balance`).
  Future<Result<Map<String, int>>> getFilledStock(
    String locationType,
    String locationId,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/inventory-locations/$locationType/$locationId/balance',
      );
      final stock = <String, int>{};
      for (final line in response.data?['balances'] as List<dynamic>? ?? []) {
        final map = line as Map<String, dynamic>;
        if (map['status'] != 'filled') continue;
        final id = map['cylinder_type_id'] as String;
        stock[id] = (stock[id] ?? 0) + (map['quantity'] as num).toInt();
      }
      return Success(stock);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Every branch (`GET /admin/branches`).
  Future<Result<List<FleetBranch>>> listBranches() async {
    try {
      final response = await _dio.get<List<dynamic>>('/api/v1/admin/branches');
      return Success([
        for (final e in response.data ?? const [])
          FleetBranch.fromJson(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Staff of one [role] (`GET /employees`), one page of up to [limit].
  Future<Result<List<FleetEmployee>>> listEmployees({
    String? role,
    int limit = 200,
  }) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/employees',
      queryParameters: {'skip': 0, 'limit': limit, 'role': ?role},
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        FleetEmployee.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Registers a staff member (`POST /employees`, needs `users:manage`).
  Future<Result<FleetEmployee>> registerEmployee({
    required String branchId,
    required String firstName,
    required String lastName,
    required String phoneNumber,
    String role = 'driver',
    String? email,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/employees',
      data: {
        'branch_id': branchId,
        'first_name': firstName,
        'last_name': lastName,
        'phone_number': phoneNumber,
        'role': role,
        'email': ?email,
      },
    );
    return FleetEmployee.fromJson(response.data!);
  });

  /// Gives a driver employee the phone login the Driver App signs in with
  /// (`POST /employees/{id}/enable-login`). Safe to repeat.
  Future<Result<void>> enableDriverLogin(String employeeId) => _guard(() async {
    await _dio.post<Map<String, dynamic>>(
      '/api/v1/employees/$employeeId/enable-login',
    );
  });

  /// Registers a driver profile (`POST /drivers`). The licence scan
  /// ([licenceDocumentRef], from [uploadDocument]) is required.
  Future<Result<FleetDriver>> registerDriver({
    required String branchId,
    required String employeeId,
    required String licenseNumber,
    required DateTime licenseExpiryDate,
    required String licenceDocumentRef,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/drivers',
      data: {
        'branch_id': branchId,
        'employee_id': employeeId,
        'license_number': licenseNumber,
        'license_expiry_date': _day(licenseExpiryDate),
        'licence_document_ref': licenceDocumentRef,
      },
    );
    return FleetDriver.fromJson(response.data!);
  });

  /// `PATCH /drivers/{id}/status`: active, on_leave or inactive (inactive is
  /// final).
  Future<Result<FleetDriver>> setDriverStatus(String id, String status) =>
      _guard(() async {
        final response = await _dio.patch<Map<String, dynamic>>(
          '/api/v1/drivers/$id/status',
          data: {'status': status},
        );
        return FleetDriver.fromJson(response.data!);
      });

  /// `PATCH /drivers/{id}/license`.
  Future<Result<FleetDriver>> updateDriverLicense(
    String id, {
    required String licenseNumber,
    DateTime? licenseExpiryDate,
  }) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/drivers/$id/license',
      data: {
        'license_number': licenseNumber,
        'license_expiry_date': licenseExpiryDate == null
            ? null
            : _day(licenseExpiryDate),
      },
    );
    return FleetDriver.fromJson(response.data!);
  });

  /// Registers a van (`POST /vehicles`). The RC scan ([rcDocumentRef], from
  /// [uploadDocument]) and its expiry are required.
  Future<Result<FleetVehicle>> registerVehicle({
    required String branchId,
    required String registrationNumber,
    required String make,
    required String model,
    required String ownershipType,
    required int capacityUnits,
    required String rcDocumentRef,
    required DateTime rcExpiryDate,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/vehicles',
      data: {
        'branch_id': branchId,
        'registration_number': registrationNumber,
        'make': make,
        'model': model,
        'ownership_type': ownershipType,
        'capacity_units': capacityUnits,
        'rc_document_ref': rcDocumentRef,
        'rc_expiry_date': _day(rcExpiryDate),
      },
    );
    return FleetVehicle.fromJson(response.data!);
  });

  /// `PATCH /vehicles/{id}/status`: active, maintenance or inactive
  /// (inactive is final).
  Future<Result<FleetVehicle>> setVehicleStatus(String id, String status) =>
      _guard(() async {
        final response = await _dio.patch<Map<String, dynamic>>(
          '/api/v1/vehicles/$id/status',
          data: {'status': status},
        );
        return FleetVehicle.fromJson(response.data!);
      });

  /// `PATCH /vehicles/{id}/details`.
  Future<Result<FleetVehicle>> updateVehicleDetails(
    String id, {
    required String make,
    required String model,
    required String ownershipType,
    required int capacityUnits,
  }) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/vehicles/$id/details',
      data: {
        'make': make,
        'model': model,
        'ownership_type': ownershipType,
        'capacity_units': capacityUnits,
      },
    );
    return FleetVehicle.fromJson(response.data!);
  });

  /// Stages a licence or RC photo (`POST /documents/attachments`) and
  /// returns the blob ref [registerDriver] / [registerVehicle] take.
  Future<Result<String>> uploadDocument({
    required List<int> bytes,
    required String filename,
    String contentType = 'image/jpeg',
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/documents/attachments',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(
          bytes,
          filename: filename,
          contentType: MediaType.parse(contentType),
        ),
      }),
    );
    return response.data!['blob_ref'] as String;
  });

  /// OCR second pass over a staged photo (`POST /documents/recognize`);
  /// [docKind] is `driving_licence` or `vehicle_rc`.
  Future<Result<RecognizedComplianceDocument>> recognizeDocument(
    String blobRef,
    String docKind,
  ) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/documents/recognize',
      data: {'blob_ref': blobRef, 'doc_kind': docKind},
    );
    return RecognizedComplianceDocument.fromJson(response.data!);
  });

  static String _day(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';

  Future<Result<T>> _guard<T>(Future<T> Function() call) async {
    try {
      return Success(await call());
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<List<T>>> _list<T>(
    String path,
    int limit,
    T Function(Map<String, dynamic>) parse,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: {'skip': 0, 'limit': limit},
      );
      return Success([
        for (final e in response.data?['items'] as List<dynamic>? ?? const [])
          parse(e as Map<String, dynamic>),
      ]);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
