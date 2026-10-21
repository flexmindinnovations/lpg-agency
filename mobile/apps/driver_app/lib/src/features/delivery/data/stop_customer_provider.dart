import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/cached_resource.dart';

/// Who to ask for at a stop: the customer's name and phone, by customer id.
/// `GET /customers/{id}` (drivers hold `customers:read`), cached so a stop
/// opened once still shows the number offline.
final stopCustomerProvider = FutureProvider.autoDispose
    .family<CustomerResponse?, String>((ref, customerId) async {
      final map = await ref
          .watch(cachedResourceProvider)
          .getMap(
            '/api/v1/customers/$customerId',
            type: 'customer',
            id: customerId,
          );
      return map == null ? null : CustomerResponse.fromJson(map);
    });
