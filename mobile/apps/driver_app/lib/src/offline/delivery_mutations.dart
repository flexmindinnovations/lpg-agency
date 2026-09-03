// Public named params (`coordinator`, `cache`) assigned to private fields —
// Dart 3 forbids private named parameters, so an initializing formal can't
// be used here.
// ignore_for_file: prefer_initializing_formals

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

import 'cached_resource.dart';
import 'sync_providers.dart';

/// Writes the driver takes on a stop or route, routed through the offline
/// queue: the local state moves optimistically now, the backend call is a
/// durable [SyncOperation] that drains when connectivity allows (ADR-008).
///
/// Every op's payload is `{path, body, aggregateId}` — the coordinator's
/// `_dispatch` reads `path`/`body`, and the app reads `aggregateId` for the
/// optimistic overlay ([pendingSyncAggregatesProvider]).
class DeliveryMutations {
  DeliveryMutations({
    required SyncCoordinator coordinator,
    required ResourceCache? cache,
  }) : _coordinator = coordinator,
       _cache = cache;

  final SyncCoordinator _coordinator;
  final ResourceCache? _cache;

  /// `ready_for_dispatch → out_for_delivery`.
  Future<void> departStop(String orderId) => _queueOrderTransition(
    orderId: orderId,
    newStatus: 'out_for_delivery',
    type: 'order_depart',
    path: '/api/v1/orders/$orderId/depart',
  );

  /// `out_for_delivery → failed_delivery`.
  Future<void> recordFailedDelivery(
    String orderId, {
    required String reasonCode,
    String? resolutionAction,
  }) => _queueOrderTransition(
    orderId: orderId,
    newStatus: 'failed_delivery',
    type: 'order_failed_delivery',
    path: '/api/v1/orders/$orderId/failed-delivery',
    body: {'reason_code': reasonCode, 'resolution_action': resolutionAction},
  );

  /// End-of-route cash declaration. No cached view to mutate — the screen
  /// shows a "queued" state off [pendingSyncAggregatesProvider] instead.
  Future<void> declareCashHandover({
    required String routeId,
    required String driverId,
    required double actualAmount,
  }) {
    return _coordinator.enqueueOperation(
      'cash_handover_declare',
      jsonEncode({
        'path': '/api/v1/cash-handovers',
        'body': {
          'driver_id': driverId,
          'route_id': routeId,
          'actual_amount': actualAmount.toStringAsFixed(2),
        },
        'aggregateId': routeId,
      }),
    );
  }

  Future<void> _queueOrderTransition({
    required String orderId,
    required String newStatus,
    required String type,
    required String path,
    Object? body,
  }) async {
    final cached = await _cache?.read('order', orderId);
    if (cached != null) {
      cached['status'] = newStatus;
      await _cache!.write('order', orderId, cached);
    }
    await _coordinator.enqueueOperation(
      type,
      jsonEncode({'path': path, 'body': body, 'aggregateId': orderId}),
    );
  }
}

final deliveryMutationsProvider = Provider<DeliveryMutations>(
  (ref) => DeliveryMutations(
    coordinator: ref.watch(syncCoordinatorProvider),
    cache: ref.watch(resourceCacheProvider),
  ),
);
