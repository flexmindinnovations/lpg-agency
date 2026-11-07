import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
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

    test('getSupportContacts parses the helpline and agency phone', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      String? path;
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        path = options.path;
        return jsonResponse({
          'emergency_helpline': '1906',
          'agency_phone': '+914012345678',
        }, 200);
      });

      final result = await ComplaintApi(client.dio).getSupportContacts();

      final contacts = result.when(onSuccess: (c) => c, onFailure: (_) => null);
      expect(path, '/api/v1/support/contacts');
      expect(contacts!.emergencyHelpline, '1906');
      expect(contacts.agencyPhone, '+914012345678');
    });

    test('parses the readable references and the assignee', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'id': 'complaint-1',
          'complaint_number': 'CMP-0007',
          'customer_id': 'customer-1',
          'category': ComplaintCategory.gasLeakSafety,
          'priority': ComplaintPriority.critical,
          'status': ComplaintStatus.assigned,
          'description': 'Smell of gas.',
          'sla_due_at': '2020-01-01T00:00:00Z',
          'created_at': '2026-08-01T00:00:00Z',
          'updated_at': '2026-08-01T00:00:00Z',
          'customer_name': 'E2E Customer',
          'customer_phone': '+919999900098',
          'order_number': 'ORD000061',
          'assignee_name': 'Anita Desai',
          'assignments': [
            {
              'id': 'a1',
              'assigned_to': 'u1',
              'assigned_at': '2026-08-01T00:00:00Z',
              'created_at': '2026-08-01T00:00:00Z',
              'assigned_to_name': 'Anita Desai',
            },
          ],
        }, 200),
      );

      final result = await ComplaintApi(client.dio).getComplaint('complaint-1');

      final c = result.when(onSuccess: (c) => c, onFailure: (_) => null)!;
      expect(c.customerName, 'E2E Customer');
      expect(c.orderNumber, 'ORD000061');
      expect(c.assigneeName, 'Anita Desai');
      expect(c.assignments.single.assignedToName, 'Anita Desai');
      expect(c.isFinished, isFalse);
      expect(c.isOverdue(DateTime(2026, 8, 2)), isTrue, reason: 'SLA passed');
    });

    test('a resolved complaint is never overdue', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'id': 'complaint-1',
          'customer_id': 'customer-1',
          'category': ComplaintCategory.other,
          'priority': ComplaintPriority.low,
          'status': ComplaintStatus.resolved,
          'description': 'Done.',
          'sla_due_at': '2020-01-01T00:00:00Z',
          'created_at': '2026-08-01T00:00:00Z',
          'updated_at': '2026-08-01T00:00:00Z',
        }, 200),
      );

      final result = await ComplaintApi(client.dio).getComplaint('complaint-1');

      final c = result.when(onSuccess: (c) => c, onFailure: (_) => null)!;
      expect(c.isFinished, isTrue);
      expect(c.isOverdue(DateTime(2026, 8, 2)), isFalse);
    });

    test('lists assignees, assigns and resolves', () async {
      final seen = <RequestOptions>[];
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen.add(options);
        if (options.path.endsWith('/assignees')) {
          return jsonResponse([
            {'user_id': 'u1', 'name': 'Anita Desai', 'role': 'manager'},
          ], 200);
        }
        return jsonResponse(<String, dynamic>{}, 204);
      });
      final api = ComplaintApi(client.dio);

      final staff = await api.getAssignees();
      await api.assign('complaint-1', 'u1');
      await api.resolve(
        'complaint-1',
        outcome: 'Compensated',
        notes: 'Refunded',
      );

      expect(
        staff.when(onSuccess: (l) => l.single.name, onFailure: (_) => null),
        'Anita Desai',
      );
      expect(seen[1].path, '/api/v1/complaints/complaint-1/assign');
      expect(seen[1].data, {'assigned_to': 'u1'});
      expect(seen[2].path, '/api/v1/complaints/complaint-1/resolve');
      expect(seen[2].data, {
        'outcome': 'Compensated',
        'resolution_notes': 'Refunded',
      });
    });

    test('getMyComplaints narrows by status and customer', () async {
      RequestOptions? seen;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen = options;
        return jsonResponse({
          'items': <Map<String, dynamic>>[],
          'total': 0,
          'skip': 0,
          'limit': 50,
        }, 200);
      });

      await ComplaintApi(
        client.dio,
      ).getMyComplaints(status: 'Open', customerId: 'customer-1');

      expect(seen!.queryParameters['status'], 'Open');
      expect(seen!.queryParameters['customer_id'], 'customer-1');
    });
  });
}
