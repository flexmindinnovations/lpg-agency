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
}
