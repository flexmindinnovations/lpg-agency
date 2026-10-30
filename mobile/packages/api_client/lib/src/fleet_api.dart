import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

import 'models/models.dart';
import 'failure_mapper.dart';

/// Hand-written wrapper for what the office needs to send an order out and
/// keep stock straight: drivers, vans, godowns, the stock at a godown or on a
/// van, and the receipts and counts that change it.
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

  /// Moves a driver to another branch (`PATCH /drivers/{id}/assignment`),
  /// keeping the same employee, as the dashboard does.
  Future<Result<FleetDriver>> moveDriverToBranch(
    String id, {
    required String employeeId,
    required String branchId,
  }) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/drivers/$id/assignment',
      data: {'employee_id': employeeId, 'branch_id': branchId},
    );
    return FleetDriver.fromJson(response.data!);
  });

  /// Everything counted at a `warehouse` or `vehicle`, one line per cylinder
  /// type and status (`GET /inventory-locations/{type}/{id}/balance`).
  Future<Result<List<StockBalanceLine>>> getBalanceLines(
    String locationType,
    String locationId,
  ) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/inventory-locations/$locationType/$locationId/balance',
    );
    return [
      for (final e in response.data?['balances'] as List<dynamic>? ?? const [])
        StockBalanceLine.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Counts already on file for a location, newest first
  /// (`GET /inventory-locations/{type}/{id}/reconciliation-records`); only
  /// those in [state] (`pending`, `approved`, `rejected`) when given.
  Future<Result<List<ReconciliationRecord>>> listReconciliations(
    String locationType,
    String locationId, {
    String? state,
  }) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/inventory-locations/$locationType/$locationId/reconciliation-records',
      queryParameters: {'state': ?state},
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        ReconciliationRecord.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Records a physical count (`POST .../reconciliation-records`); stock
  /// doesn't change until someone approves it.
  Future<Result<ReconciliationRecord>> recordCount(
    String locationType,
    String locationId, {
    required String cylinderTypeId,
    required String status,
    required int actualQuantity,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/inventory-locations/$locationType/$locationId/reconciliation-records',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'status': status,
        'actual_quantity': actualQuantity,
      },
    );
    return ReconciliationRecord.fromJson(response.data!);
  });

  /// Approves a pending count and books its variance
  /// (`POST /reconciliation-records/{id}/approve`). `409
  /// SELF_APPROVAL_NOT_ALLOWED` for the person who counted, unless admin.
  Future<Result<ReconciliationRecord>> approveCount(String recordId) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/api/v1/reconciliation-records/$recordId/approve',
        );
        return ReconciliationRecord.fromJson(response.data!);
      });

  /// Closes a pending count without changing stock
  /// (`POST /reconciliation-records/{id}/reject`), e.g. when it needs a
  /// recount. [reason] is at least three characters.
  Future<Result<ReconciliationRecord>> rejectCount(
    String recordId, {
    required String reason,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/reconciliation-records/$recordId/reject',
      data: {'reason': reason},
    );
    return ReconciliationRecord.fromJson(response.data!);
  });

  /// Cylinder types at or below their reorder point
  /// (`GET /inventory/reorder-signals`), across every godown.
  Future<Result<List<ReorderSignal>>> listReorderSignals() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/inventory/reorder-signals',
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        ReorderSignal.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// The latest movements at a `warehouse` or `vehicle`, newest first
  /// (`GET /inventory-locations/{type}/{id}/transactions`).
  Future<Result<List<InventoryTransaction>>> listTransactions(
    String locationType,
    String locationId, {
    int limit = 20,
  }) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/inventory-locations/$locationType/$locationId/transactions',
      queryParameters: {'limit': limit},
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        InventoryTransaction.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Records filled cylinders arriving at a godown
  /// (`POST /warehouses/{id}/goods-receipt-notes`). [sourceOmc] is `iocl`,
  /// `bpcl`, `hpcl` or `other`.
  Future<Result<GoodsReceipt>> recordGoodsReceipt(
    String warehouseId, {
    required String cylinderTypeId,
    required int quantity,
    String? sourceOmc,
    String? challanNumber,
    String? invoiceNumber,
    String? truckNumber,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/warehouses/$warehouseId/goods-receipt-notes',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'quantity_received': quantity,
        'source_omc': ?sourceOmc,
        'challan_number': ?challanNumber,
        'invoice_number': ?invoiceNumber,
        'truck_number': ?truckNumber,
      },
    );
    return GoodsReceipt.fromJson(response.data!);
  });

  /// Documents on file across the agency (`GET /compliance-documents`),
  /// soonest expiry first. [expiry] is `expiring` (within 30 days), `expired`
  /// or `upcoming` (overdue or due within 90 days, the compliance calendar);
  /// every document when `null`. [ownerType] narrows to `driver`, `vehicle`,
  /// `warehouse` or `tenant`.
  Future<Result<List<ComplianceDocument>>> listComplianceDocuments({
    String? expiry = 'upcoming',
    String? ownerType,
    int limit = 200,
  }) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/compliance-documents',
      queryParameters: {
        'expiry': ?expiry,
        'owner_type': ?ownerType,
        'limit': limit,
      },
    );
    return [
      for (final e in response.data?['items'] as List<dynamic>? ?? const [])
        ComplianceDocument.fromJson(e as Map<String, dynamic>),
    ];
  });

  /// Replaces a document with its renewal (`PUT /compliance-documents/{id}`);
  /// the new scan ([fileRef], from [uploadDocument]) goes back to pending
  /// verification. Needs `drivers:manage`.
  Future<Result<ComplianceDocument>> renewDocument(
    String documentId, {
    required String documentNumber,
    required String fileRef,
    DateTime? issueDate,
    DateTime? expiryDate,
  }) => _guard(() async {
    final response = await _dio.put<Map<String, dynamic>>(
      '/api/v1/compliance-documents/$documentId',
      data: {
        'document_number': documentNumber,
        'file_ref': fileRef,
        'issue_date': issueDate == null ? null : _day(issueDate),
        'expiry_date': expiryDate == null ? null : _day(expiryDate),
      },
    );
    return ComplianceDocument.fromJson(response.data!);
  });

  /// The status moves the server allows (`GET /inventory/status-transitions`).
  Future<Result<StatusTransitions>> getStatusTransitions() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/inventory/status-transitions',
    );
    return StatusTransitions.fromJson(response.data!);
  });

  /// Moves cylinders from one status to another at a godown or van, such as
  /// filled to leaking (`POST .../status-changes`). Needs `inventory:load`;
  /// `409 INVALID_STATUS_TRANSITION` when the pair is not allowed.
  Future<Result<void>> changeStatus(
    String locationType,
    String locationId, {
    required String cylinderTypeId,
    required String fromStatus,
    required String toStatus,
    required int quantity,
  }) => _guard(() async {
    await _dio.post<dynamic>(
      '/api/v1/inventory-locations/$locationType/$locationId/status-changes',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'from_status': fromStatus,
        'to_status': toStatus,
        'quantity': quantity,
      },
    );
  });

  /// A manual correction of the books (`POST .../adjustments`), with the
  /// [reason] kept on record. Needs `inventory:adjust`.
  Future<Result<void>> adjustStock(
    String locationType,
    String locationId, {
    required String cylinderTypeId,
    required String fromStatus,
    required String toStatus,
    required int quantity,
    required String reason,
  }) => _guard(() async {
    await _dio.post<dynamic>(
      '/api/v1/inventory-locations/$locationType/$locationId/adjustments',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'from_status': fromStatus,
        'to_status': toStatus,
        'quantity': quantity,
        'reason': reason,
      },
    );
  });

  /// Sends empties, or defective cylinders, back to the oil company's plant
  /// (`POST /warehouses/{id}/omc-returns`). [status] is `empty`, `damaged`,
  /// `leakage` or `quarantine`; `409 INSUFFICIENT_STOCK` when the godown
  /// holds fewer.
  Future<Result<OmcReturn>> returnToOmc(
    String warehouseId, {
    required String cylinderTypeId,
    required int quantity,
    required String destinationOmc,
    String status = 'empty',
    String? challanNumber,
    String? truckNumber,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/warehouses/$warehouseId/omc-returns',
      data: {
        'cylinder_type_id': cylinderTypeId,
        'quantity': quantity,
        'destination_omc': destinationOmc,
        'status': status,
        'challan_number': ?challanNumber,
        'truck_number': ?truckNumber,
      },
    );
    return OmcReturn.fromJson(response.data!);
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
