import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('ComplaintApi', () {
    test('getMyComplaints parses the skip/limit pagination shape', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'items': [
            {
              'id': 'complaint-1',
              'customer_id': 'customer-1',
              'category': ComplaintCategory.lateDelivery,
              'priority': ComplaintPriority.medium,
              'status': ComplaintStatus.open,
              'description': 'Delivery arrived a day late.',
              'created_at': '2026-08-01T00:00:00Z',
              'updated_at': '2026-08-01T00:00:00Z',
            },
          ],
          'total': 1,
          'skip': 0,
          'limit': 50,
        }, 200),
      );
      final complaintApi = ComplaintApi(client.dio);

      final result = await complaintApi.getMyComplaints();

      final page = result.when(onSuccess: (p) => p, onFailure: (_) => null);
      expect(page, isNotNull);
      expect(page!.skip, 0);
      expect(page.limit, 50);
      expect(page.items.single.category, ComplaintCategory.lateDelivery);
      expect(page.items.single.assignments, isEmpty);
      expect(page.items.single.resolution, isNull);
    });

    test(
      'raiseComplaint returns the bare id from a {"id": ...} response',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter(
          (options) => jsonResponse({'id': 'complaint-new'}, 201),
        );
        final complaintApi = ComplaintApi(client.dio);

        final result = await complaintApi.raiseComplaint(
          const RaiseComplaintRequest(
            customerId: 'customer-1',
            category: ComplaintCategory.damagedCylinder,
            priority: ComplaintPriority.high,
            description: 'Cylinder was leaking on arrival.',
          ),
        );

        expect(
          result.when(onSuccess: (id) => id, onFailure: (_) => null),
          'complaint-new',
        );
      },
    );
  });
}
