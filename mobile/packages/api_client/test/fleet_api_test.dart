import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('FleetApi', () {
    test('listDrivers parses names and status', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/drivers');
        return jsonResponse({
          'items': [
            {
              'id': 'd-1',
              'branch_id': 'b-1',
              'name': 'Ravi Kumar',
              'status': 'active',
            },
          ],
          'total': 1,
        }, 200);
      });

      final result = await FleetApi(client.dio).listDrivers();

      final drivers = result.when(onSuccess: (d) => d, onFailure: (_) => null);
      expect(drivers!.single.name, 'Ravi Kumar');
      expect(drivers.single.isActive, isTrue);
    });

    test('listWarehouses parses the plain list', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/admin/warehouses');
        return jsonResponse([
          {
            'id': 'w-1',
            'branch_id': 'b-1',
            'name': 'Main godown',
            'address_line': 'Plot 4',
            'is_active': true,
          },
        ], 200);
      });

      final result = await FleetApi(client.dio).listWarehouses();

      final godowns = result.when(onSuccess: (w) => w, onFailure: (_) => null);
      expect(godowns!.single.name, 'Main godown');
    });

    test('getFilledStock sums only filled cylinders per type', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(
          options.path,
          '/api/v1/inventory-locations/warehouse/w-1/balance',
        );
        return jsonResponse({
          'balances': [
            {'cylinder_type_id': 'ct-1', 'status': 'filled', 'quantity': 4},
            {'cylinder_type_id': 'ct-1', 'status': 'filled', 'quantity': 2},
            {'cylinder_type_id': 'ct-1', 'status': 'empty', 'quantity': 9},
            {'cylinder_type_id': 'ct-2', 'status': 'empty', 'quantity': 3},
          ],
        }, 200);
      });

      final result = await FleetApi(
        client.dio,
      ).getFilledStock('warehouse', 'w-1');

      final stock = result.when(onSuccess: (s) => s, onFailure: (_) => null);
      expect(stock, {'ct-1': 6});
    });

    test('registerDriver posts the licence details and scan ref', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'POST');
        expect(options.path, '/api/v1/drivers');
        expect(options.data, {
          'branch_id': 'b-1',
          'employee_id': 'e-1',
          'license_number': 'MH12 2020 0001',
          'license_expiry_date': '2031-03-07',
          'licence_document_ref': 'tenant/t/compliance-staging/x.jpg',
        });
        return jsonResponse({
          'id': 'd-1',
          'branch_id': 'b-1',
          'name': 'Ravi Kumar',
          'status': 'active',
          'employee_id': 'e-1',
          'license_number': 'MH12 2020 0001',
          'license_expiry_date': '2031-03-07',
          'identity_user_id': null,
        }, 201);
      });

      final result = await FleetApi(client.dio).registerDriver(
        branchId: 'b-1',
        employeeId: 'e-1',
        licenseNumber: 'MH12 2020 0001',
        licenseExpiryDate: DateTime(2031, 3, 7),
        licenceDocumentRef: 'tenant/t/compliance-staging/x.jpg',
      );

      final driver = result.when(onSuccess: (d) => d, onFailure: (_) => null);
      expect(driver!.hasLogin, isFalse);
      expect(driver.licenseExpiryDate, DateTime(2031, 3, 7));
    });

    test('registerVehicle posts the RC details', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/vehicles');
        expect(options.data['registration_number'], 'MH12AB1234');
        expect(options.data['capacity_units'], 20);
        expect(options.data['rc_expiry_date'], '2030-01-02');
        return jsonResponse({
          'id': 'v-1',
          'branch_id': 'b-1',
          'registration_number': 'MH12AB1234',
          'make': 'Tata',
          'model': 'Ace',
          'ownership_type': 'owned',
          'capacity_units': 20,
          'status': 'active',
        }, 201);
      });

      final result = await FleetApi(client.dio).registerVehicle(
        branchId: 'b-1',
        registrationNumber: 'MH12AB1234',
        make: 'Tata',
        model: 'Ace',
        ownershipType: 'owned',
        capacityUnits: 20,
        rcDocumentRef: 'tenant/t/compliance-staging/rc.jpg',
        rcExpiryDate: DateTime(2030, 1, 2),
      );

      final van = result.when(onSuccess: (v) => v, onFailure: (_) => null);
      expect(van!.make, 'Tata');
      expect(van.ownershipType, 'owned');
    });

    test('setDriverStatus and setVehicleStatus patch the status', () async {
      final paths = <String>[];
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        paths.add('${options.method} ${options.path}');
        expect(options.data, {'status': 'on_leave'});
        return jsonResponse(
          options.path.contains('drivers')
              ? {'id': 'd-1', 'branch_id': 'b-1', 'status': 'on_leave'}
              : {
                  'id': 'v-1',
                  'branch_id': 'b-1',
                  'registration_number': 'X',
                  'status': 'on_leave',
                },
          200,
        );
      });
      final api = FleetApi(client.dio);

      await api.setDriverStatus('d-1', 'on_leave');
      await api.setVehicleStatus('v-1', 'on_leave');

      expect(paths, [
        'PATCH /api/v1/drivers/d-1/status',
        'PATCH /api/v1/vehicles/v-1/status',
      ]);
    });

    test('uploadDocument posts multipart and returns the blob ref', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/documents/attachments');
        expect(options.data, isA<FormData>());
        return jsonResponse({'blob_ref': 'tenant/t/compliance-staging/a'}, 201);
      });

      final result = await FleetApi(
        client.dio,
      ).uploadDocument(bytes: [1, 2, 3], filename: 'dl.jpg');

      expect(
        result.when(onSuccess: (r) => r, onFailure: (_) => null),
        'tenant/t/compliance-staging/a',
      );
    });

    test('recognizeDocument prefers the transport validity', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.data, {
          'blob_ref': 'ref',
          'doc_kind': 'driving_licence',
        });
        return jsonResponse({
          'doc_kind': 'driving_licence',
          'confidence': 0.9,
          'document_number': 'MH1220200001',
          'valid_till': '2030-05-01',
          'transport_valid_till': '2028-05-01',
        }, 200);
      });

      final result = await FleetApi(
        client.dio,
      ).recognizeDocument('ref', 'driving_licence');

      final doc = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(doc!.validTill, DateTime(2028, 5, 1));
      expect(doc.documentNumber, 'MH1220200001');
    });

    test('cancelRoute patches the trip to cancelled', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'PATCH');
        expect(options.path, '/api/v1/routes/r-1/status');
        expect(options.data, {'status': 'cancelled'});
        return jsonResponse({
          'id': 'r-1',
          'status': 'cancelled',
          'driver_id': 'd-1',
          'vehicle_id': 'v-1',
          'stops': <Object>[],
        }, 200);
      });

      final result = await RouteApi(client.dio).cancelRoute('r-1');

      expect(
        result.when(onSuccess: (r) => r.status, onFailure: (_) => null),
        'cancelled',
      );
    });

    test('moveDriverToBranch patches the assignment', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'PATCH');
        expect(options.path, '/api/v1/drivers/d-1/assignment');
        expect(options.data, {'employee_id': 'e-1', 'branch_id': 'b-2'});
        return jsonResponse({
          'id': 'd-1',
          'branch_id': 'b-2',
          'status': 'active',
        }, 200);
      });

      final result = await FleetApi(
        client.dio,
      ).moveDriverToBranch('d-1', employeeId: 'e-1', branchId: 'b-2');

      expect(
        result.when(onSuccess: (d) => d.branchId, onFailure: (_) => null),
        'b-2',
      );
    });

    test('recordCount and approveCount drive a van reconciliation', () async {
      final calls = <String>[];
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        calls.add('${options.method} ${options.path}');
        return jsonResponse({
          'id': 'rec-1',
          'cylinder_type_id': 'ct-1',
          'status': 'empty',
          'expected_quantity': 5,
          'actual_quantity': 4,
          'variance': -1,
          'state': options.path.endsWith('/approve') ? 'approved' : 'pending',
        }, 201);
      });
      final api = FleetApi(client.dio);

      final recorded = await api.recordCount(
        'vehicle',
        'v-1',
        cylinderTypeId: 'ct-1',
        status: 'empty',
        actualQuantity: 4,
      );
      final approved = await api.approveCount('rec-1');

      expect(
        recorded.when(onSuccess: (r) => r.isPending, onFailure: (_) => null),
        isTrue,
      );
      expect(
        approved.when(onSuccess: (r) => r.state, onFailure: (_) => null),
        'approved',
      );
      expect(calls, [
        'POST /api/v1/inventory-locations/vehicle/v-1/reconciliation-records',
        'POST /api/v1/reconciliation-records/rec-1/approve',
      ]);
    });

    test('getBalanceLines keeps every status', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'balances': [
            {'cylinder_type_id': 'ct-1', 'status': 'filled', 'quantity': 2},
            {'cylinder_type_id': 'ct-1', 'status': 'empty', 'quantity': 3},
          ],
        }, 200),
      );

      final result = await FleetApi(
        client.dio,
      ).getBalanceLines('vehicle', 'v-1');

      final lines = result.when(onSuccess: (l) => l, onFailure: (_) => null);
      expect(lines!.map((l) => l.status), ['filled', 'empty']);
    });

    test(
      'settleRoute posts to reconcile and reports a pending count',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          expect(options.path, '/api/v1/routes/r-1/reconcile');
          return jsonResponse({
            'error_code': 'ROUTE_RECONCILIATION_PENDING',
            'detail': 'No approved reconciliation yet.',
          }, 409);
        });

        final result = await RouteApi(client.dio).settleRoute('r-1');

        final failure = result.when(
          onSuccess: (_) => null,
          onFailure: (f) => f,
        );
        expect(failure?.errorCode, 'ROUTE_RECONCILIATION_PENDING');
      },
    );

    test('optimizeRoute parses the saved distance', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/routes/r-1/optimize');
        return jsonResponse({
          'route': {
            'id': 'r-1',
            'status': 'loaded',
            'driver_id': 'd-1',
            'vehicle_id': 'v-1',
            'stops': <Object>[],
          },
          'km_before': 12.5,
          'km_after': 9.0,
          'km_saved': 3.5,
        }, 200);
      });

      final result = await RouteApi(client.dio).optimizeRoute('r-1');

      expect(
        result.when(onSuccess: (o) => o.kmSaved, onFailure: (_) => null),
        3.5,
      );
    });
  });
  group('FleetApi stock', () {
    test('listReorderSignals reads the godown, stock and thresholds', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/inventory/reorder-signals');
        return jsonResponse({
          'items': [
            {
              'policy_id': 'p-1',
              'inventory_location_id': 'l-1',
              'location_ref_id': 'w-1',
              'cylinder_type_id': 'c-1',
              'on_hand': 4,
              'reorder_point': 20,
              'safety_stock': 5,
              'last_reorder_notified_at': null,
            },
          ],
        }, 200);
      });

      final result = await FleetApi(client.dio).listReorderSignals();

      final signal = result
          .when(onSuccess: (s) => s, onFailure: (_) => null)!
          .single;
      expect(signal.warehouseId, 'w-1');
      expect(signal.onHand, 4);
      expect(signal.reorderPoint, 20);
      expect(signal.isCritical, isTrue);
    });

    test('listTransactions asks for a page and parses each movement', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(
          options.path,
          '/api/v1/inventory-locations/warehouse/w-1/transactions',
        );
        expect(options.queryParameters['limit'], 5);
        return jsonResponse({
          'items': [
            {
              'id': 't-1',
              'tenant_id': 'x',
              'inventory_location_id': 'l-1',
              'cylinder_type_id': 'c-1',
              'transaction_type': 'grn_receipt',
              'from_status': null,
              'to_status': 'filled',
              'quantity': 40,
              'reference_order_id': null,
              'reason': null,
              'performed_by': 'u-1',
              'performed_at': '2026-10-30T05:30:00Z',
            },
          ],
          'next_cursor': null,
        }, 200);
      });

      final result = await FleetApi(
        client.dio,
      ).listTransactions('warehouse', 'w-1', limit: 5);

      final t = result
          .when(onSuccess: (r) => r, onFailure: (_) => null)!
          .single;
      expect(t.type, 'grn_receipt');
      expect(t.fromStatus, isNull);
      expect(t.toStatus, 'filled');
      expect(t.quantity, 40);
    });

    test('recordGoodsReceipt sends only what was filled in', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'POST');
        expect(options.path, '/api/v1/warehouses/w-1/goods-receipt-notes');
        expect(options.data, {
          'cylinder_type_id': 'c-1',
          'quantity_received': 40,
          'source_omc': 'iocl',
          'truck_number': 'MH12AB1234',
        });
        return jsonResponse({
          'id': 'g-1',
          'grn_number': 'GRN-2026-000007',
          'tenant_id': 'x',
          'warehouse_id': 'w-1',
          'cylinder_type_id': 'c-1',
          'quantity_received': 40,
          'source_omc': 'iocl',
          'received_by': 'u-1',
          'received_at': '2026-10-30T05:30:00Z',
        }, 201);
      });

      final result = await FleetApi(client.dio).recordGoodsReceipt(
        'w-1',
        cylinderTypeId: 'c-1',
        quantity: 40,
        sourceOmc: 'iocl',
        truckNumber: 'MH12AB1234',
      );

      final grn = result.when(onSuccess: (g) => g, onFailure: (_) => null)!;
      expect(grn.grnNumber, 'GRN-2026-000007');
      expect(grn.quantity, 40);
    });

    test(
      'listReconciliations filters by state and rejectCount posts why',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        final seen = <String>[];
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          seen.add('${options.method} ${options.path}');
          if (options.method == 'GET') {
            expect(options.queryParameters, {'state': 'pending'});
            return jsonResponse({'items': <Object>[]}, 200);
          }
          expect(options.data, {'reason': 'Count again'});
          return jsonResponse({
            'id': 'r-1',
            'cylinder_type_id': 'c-1',
            'status': 'filled',
            'expected_quantity': 42,
            'actual_quantity': 40,
            'variance': -2,
            'state': 'rejected',
          }, 200);
        });
        final api = FleetApi(client.dio);

        await api.listReconciliations('warehouse', 'w-1', state: 'pending');
        final rejected = await api.rejectCount('r-1', reason: 'Count again');

        expect(seen, [
          'GET /api/v1/inventory-locations/warehouse/w-1/reconciliation-records',
          'POST /api/v1/reconciliation-records/r-1/reject',
        ]);
        expect(
          rejected.when(onSuccess: (r) => r.state, onFailure: (_) => null),
          'rejected',
        );
      },
    );
  });
  group('FleetApi compliance documents', () {
    Map<String, Object?> doc({String? expiry = '2026-11-10'}) => {
      'id': 'd-1',
      'owner_type': 'vehicle',
      'owner_id': 'v-1',
      'doc_type': 'vehicle_insurance',
      'document_number': 'POL-123',
      'file_url': null,
      'issue_date': '2025-11-11',
      'expiry_date': expiry,
      'verification_status': 'pending',
      'rejection_reason': null,
      'verified_at': null,
    };

    test(
      'listComplianceDocuments asks for what is overdue or due soon',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          expect(options.path, '/api/v1/compliance-documents');
          expect(options.queryParameters, {'expiry': 'upcoming', 'limit': 200});
          return jsonResponse({
            'items': [doc(), doc(expiry: null)],
            'total': 2,
          }, 200);
        });

        final result = await FleetApi(client.dio).listComplianceDocuments();

        final docs = result.when(onSuccess: (d) => d, onFailure: (_) => null)!;
        expect(docs, hasLength(2));
        expect(docs.first.docType, 'vehicle_insurance');
        expect(docs.first.ownerType, 'vehicle');
        expect(docs.first.expiryDate, DateTime.parse('2026-11-10'));
        expect(docs.last.expiryDate, isNull);
      },
    );

    test('daysLeft counts calendar days and goes negative once lapsed', () {
      final d = ComplianceDocument.fromJson(doc(expiry: '2026-11-10'));
      expect(d.daysLeft(DateTime(2026, 10, 30, 23, 59)), 11);
      expect(d.daysLeft(DateTime(2026, 11, 10)), 0);
      expect(d.daysLeft(DateTime(2026, 11, 12)), -2);
      expect(ComplianceDocument.fromJson(doc(expiry: null)).daysLeft(), isNull);
    });

    test('renewDocument sends the new scan, number and dates', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'PUT');
        expect(options.path, '/api/v1/compliance-documents/d-1');
        expect(options.data, {
          'document_number': 'POL-456',
          'file_ref': 'blob/abc',
          'issue_date': '2026-10-30',
          'expiry_date': '2027-10-29',
        });
        return jsonResponse(doc(expiry: '2027-10-29'), 200);
      });

      final result = await FleetApi(client.dio).renewDocument(
        'd-1',
        documentNumber: 'POL-456',
        fileRef: 'blob/abc',
        issueDate: DateTime(2026, 10, 30),
        expiryDate: DateTime(2027, 10, 29),
      );

      expect(
        result.when(onSuccess: (d) => d.expiryDate, onFailure: (_) => null),
        DateTime.parse('2027-10-29'),
      );
    });
  });
  group('FleetApi stock moves', () {
    test('getStatusTransitions reads the allowed moves', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/inventory/status-transitions');
        return jsonResponse({
          'status_change': {
            'filled': ['leakage', 'damaged'],
          },
          'adjustment': {
            'empty': ['filled'],
          },
        }, 200);
      });

      final result = await FleetApi(client.dio).getStatusTransitions();

      final t = result.when(onSuccess: (t) => t, onFailure: (_) => null)!;
      expect(t.statusChange['filled'], ['leakage', 'damaged']);
      expect(t.adjustment['empty'], ['filled']);
    });

    test('changeStatus and adjustStock post to their own routes', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      final seen = <String>[];
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen.add('${options.method} ${options.path}');
        return jsonResponse({'balances': <Object>[]}, 201);
      });
      final api = FleetApi(client.dio);

      await api.changeStatus(
        'warehouse',
        'w-1',
        cylinderTypeId: 'c-1',
        fromStatus: 'filled',
        toStatus: 'leakage',
        quantity: 2,
      );
      await api.adjustStock(
        'warehouse',
        'w-1',
        cylinderTypeId: 'c-1',
        fromStatus: 'empty',
        toStatus: 'filled',
        quantity: 1,
        reason: 'Miscounted at receipt',
      );

      expect(seen, [
        'POST /api/v1/inventory-locations/warehouse/w-1/status-changes',
        'POST /api/v1/inventory-locations/warehouse/w-1/adjustments',
      ]);
    });

    test('returnToOmc names the plant and what is going back', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/warehouses/w-1/omc-returns');
        expect(options.data, {
          'cylinder_type_id': 'c-1',
          'quantity': 20,
          'destination_omc': 'iocl',
          'status': 'empty',
          'truck_number': 'MH12AB1234',
        });
        return jsonResponse({
          'id': 'r-1',
          'return_number': 'OMR-2026-000003',
          'warehouse_id': 'w-1',
          'cylinder_type_id': 'c-1',
          'status': 'empty',
          'quantity': 20,
          'destination_omc': 'iocl',
          'challan_number': null,
          'truck_number': 'MH12AB1234',
          'dispatched_by': 'u-1',
          'dispatched_at': '2026-10-30T09:00:00Z',
        }, 201);
      });

      final result = await FleetApi(client.dio).returnToOmc(
        'w-1',
        cylinderTypeId: 'c-1',
        quantity: 20,
        destinationOmc: 'iocl',
        truckNumber: 'MH12AB1234',
      );

      expect(
        result.when(onSuccess: (r) => r.returnNumber, onFailure: (_) => null),
        'OMR-2026-000003',
      );
    });
  });
}
