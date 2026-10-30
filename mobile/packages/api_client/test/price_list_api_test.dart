import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

Map<String, Object?> _entry({String price = '905.50', String? branch}) => {
  'id': 'p-1',
  'cylinder_type_id': 'c-1',
  'customer_type': 'domestic',
  'branch_id': branch,
  'price': price,
  'effective_from': '2026-10-30T00:00:00Z',
};

void main() {
  group('PriceListApi', () {
    test('listPrices reads decimal strings and the branch', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/admin/price-list');
        return jsonResponse([
          _entry(),
          _entry(price: '910', branch: 'b-1'),
        ], 200);
      });

      final result = await PriceListApi(client.dio).listPrices();

      final prices = result.when(onSuccess: (p) => p, onFailure: (_) => null)!;
      expect(prices.first.price, 905.5);
      expect(prices.first.branchId, isNull);
      expect(prices.last.price, 910);
      expect(prices.last.branchId, 'b-1');
      expect(prices.first.effectiveFrom, DateTime.utc(2026, 10, 30));
    });

    test('setPrice sends the paise exactly and only what was given', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'POST');
        expect(options.path, '/api/v1/admin/price-list');
        expect(options.data, {
          'cylinder_type_id': 'c-1',
          'customer_type': 'domestic',
          'price': '905.50',
        });
        return jsonResponse(_entry(), 201);
      });

      final result = await PriceListApi(
        client.dio,
      ).setPrice(cylinderTypeId: 'c-1', customerType: 'domestic', price: 905.5);

      expect(
        result.when(onSuccess: (p) => p.price, onFailure: (_) => null),
        905.5,
      );
    });

    test('setPrice carries a branch and a start date when given', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.data['branch_id'], 'b-1');
        expect(options.data['effective_from'], '2026-11-01T00:00:00.000Z');
        return jsonResponse(_entry(branch: 'b-1'), 201);
      });

      await PriceListApi(client.dio).setPrice(
        cylinderTypeId: 'c-1',
        customerType: 'domestic',
        price: 910,
        branchId: 'b-1',
        effectiveFrom: DateTime.utc(2026, 11, 1),
      );
    });

    test('listProposals and reviewProposal use the review route', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      final seen = <String>[];
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen.add('${options.method} ${options.path}');
        if (options.method == 'GET') {
          return jsonResponse({
            'items': [
              {
                'id': 'r-1',
                'cylinder_type_id': 'c-1',
                'customer_type': 'domestic',
                'branch_id': null,
                'proposed_price': '915.00',
                'effective_from': '2026-11-01T00:00:00Z',
                'source_url': 'https://omc.test/rates',
                'status': 'pending',
                'fetched_at': '2026-10-30T00:00:00Z',
                'reviewed_by': null,
                'reviewed_at': null,
              },
            ],
          }, 200);
        }
        expect(options.data, {'action': 'reject'});
        return jsonResponse({}, 200);
      });
      final api = PriceListApi(client.dio);

      final list = await api.listProposals();
      final review = await api.reviewProposal('r-1', accept: false);

      final proposal = list
          .when(onSuccess: (p) => p, onFailure: (_) => null)!
          .single;
      expect(proposal.proposedPrice, 915);
      expect(proposal.sourceUrl, 'https://omc.test/rates');
      expect(
        review.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
      expect(seen, [
        'GET /api/v1/admin/price-list/proposals',
        'PATCH /api/v1/admin/price-list/proposals/r-1',
      ]);
    });
  });
}
