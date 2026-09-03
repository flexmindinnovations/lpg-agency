// Public named params assigned to private fields — Dart 3 forbids private
// named parameters, so an initializing formal can't be used here.
// ignore_for_file: prefer_initializing_formals

import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';
import 'package:uuid/uuid.dart';

import '../api_provider.dart';
import 'cached_resource.dart';
import 'connectivity.dart';
import 'media_store_provider.dart';
import 'sync_providers.dart';

/// The outcome of [DeliveryMutations.recordDelivery].
sealed class DeliverOutcome {
  const DeliverOutcome();
}

/// Delivered online — the server confirmed it.
class DeliverSynced extends DeliverOutcome {
  const DeliverSynced();
}

/// Saved offline (or after an online network drop) — queued to sync later.
class DeliverQueued extends DeliverOutcome {
  const DeliverQueued();
}

/// The server rejected it (wrong OTP, validation) — the driver must fix it.
class DeliverFailed extends DeliverOutcome {
  const DeliverFailed(this.message);
  final String message;
}

/// Writes the driver takes on a stop or route. Simple transitions go straight
/// through the offline queue; proof-of-delivery goes inline when online (so a
/// wrong OTP is caught immediately) and falls back to the queue — media and
/// all — when offline (ADR-008).
class DeliveryMutations {
  DeliveryMutations({
    required SyncCoordinator coordinator,
    required ResourceCache? cache,
    required OrderApi orderApi,
    required ConnectivityMonitor connectivity,
    required MediaStore mediaStore,
  }) : _coordinator = coordinator,
       _cache = cache,
       _orderApi = orderApi,
       _connectivity = connectivity,
       _mediaStore = mediaStore;

  final SyncCoordinator _coordinator;
  final ResourceCache? _cache;
  final OrderApi _orderApi;
  final ConnectivityMonitor _connectivity;
  final MediaStore _mediaStore;

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

  /// The driver confirms the van matches the load manifest. Optimistically
  /// stamps `load_confirmed_at` on the cached active route so the screen and
  /// the Today nudge update immediately.
  Future<void> confirmLoad(String routeId) async {
    final cached = await _cache?.read('route_active', 'current');
    if (cached != null && cached['id'] == routeId) {
      cached['load_confirmed_at'] = DateTime.now().toUtc().toIso8601String();
      await _cache!.write('route_active', 'current', cached);
    }
    await _coordinator.enqueueOperation(
      'route_confirm_load',
      jsonEncode({
        'path': '/api/v1/routes/$routeId/confirm-load',
        'body': null,
        'aggregateId': routeId,
      }),
    );
  }

  /// `out_for_delivery → delivered` with proof of delivery.
  Future<DeliverOutcome> recordDelivery({
    required String orderId,
    required List<DeliveredLineRequest> lines,
    required String otpCode,
    required double gpsLat,
    required double gpsLng,
    required String paymentMethod,
    required double amountCollected,
    required List<int> signatureBytes,
    required List<int> photoBytes,
  }) async {
    if (await _isOnline()) {
      final inline = await _deliverInline(
        orderId: orderId,
        lines: lines,
        otpCode: otpCode,
        gpsLat: gpsLat,
        gpsLng: gpsLng,
        paymentMethod: paymentMethod,
        amountCollected: amountCollected,
        signatureBytes: signatureBytes,
        photoBytes: photoBytes,
      );
      // `null` here means "the network dropped mid-submit" — fall through to
      // the queue rather than making the driver recapture everything.
      if (inline != null) return inline;
    }

    await _queueDelivery(
      orderId: orderId,
      lines: lines,
      otpCode: otpCode,
      gpsLat: gpsLat,
      gpsLng: gpsLng,
      paymentMethod: paymentMethod,
      amountCollected: amountCollected,
      signatureBytes: signatureBytes,
      photoBytes: photoBytes,
    );
    return const DeliverQueued();
  }

  Future<bool> _isOnline() async {
    try {
      return await _connectivity.isOnline;
    } catch (_) {
      return true;
    }
  }

  /// Returns `null` when the failure was a network error (caller should
  /// queue instead), otherwise a terminal [DeliverOutcome].
  Future<DeliverOutcome?> _deliverInline({
    required String orderId,
    required List<DeliveredLineRequest> lines,
    required String otpCode,
    required double gpsLat,
    required double gpsLng,
    required String paymentMethod,
    required double amountCollected,
    required List<int> signatureBytes,
    required List<int> photoBytes,
  }) async {
    final sig = await _orderApi.uploadPodAttachment(
      orderId,
      bytes: signatureBytes,
      filename: 'signature.png',
    );
    if (sig case FailureResult(:final failure)) {
      return _outcomeFor(failure);
    }
    final photo = await _orderApi.uploadPodAttachment(
      orderId,
      bytes: photoBytes,
      filename: 'delivery.jpg',
      contentType: 'image/jpeg',
    );
    if (photo case FailureResult(:final failure)) {
      return _outcomeFor(failure);
    }

    final result = await _orderApi.deliverOrder(
      orderId,
      DeliverOrderRequest(
        lines: lines,
        otpCode: otpCode,
        proofOfDelivery: ProofOfDeliverySubmission(
          signatureBlobRef: (sig as Success).value.blobRef,
          photoBlobRef: (photo as Success).value.blobRef,
          gpsLat: gpsLat,
          gpsLng: gpsLng,
          paymentMethod: paymentMethod,
          amountCollected: amountCollected,
        ),
      ),
    );
    return switch (result) {
      Success() => const DeliverSynced(),
      FailureResult(:final failure) => _outcomeFor(failure),
    };
  }

  DeliverOutcome? _outcomeFor(Failure failure) =>
      failure.errorCode == 'NETWORK_UNAVAILABLE'
      ? null
      : DeliverFailed(failure.message);

  Future<void> _queueDelivery({
    required String orderId,
    required List<DeliveredLineRequest> lines,
    required String otpCode,
    required double gpsLat,
    required double gpsLng,
    required String paymentMethod,
    required double amountCollected,
    required List<int> signatureBytes,
    required List<int> photoBytes,
  }) async {
    final mediaId = const Uuid().v4();
    final sigKey = 'pod/$mediaId/signature.png';
    final photoKey = 'pod/$mediaId/delivery.jpg';
    await _mediaStore.write(sigKey, signatureBytes);
    await _mediaStore.write(photoKey, photoBytes);

    final cached = await _cache?.read('order', orderId);
    if (cached != null) {
      cached['status'] = 'delivered';
      await _cache!.write('order', orderId, cached);
    }

    await _coordinator.enqueueOperation(
      'order_deliver',
      jsonEncode({
        'path': '/api/v1/orders/$orderId/deliver',
        'uploadPath': '/api/v1/orders/$orderId/pod-attachments',
        'aggregateId': orderId,
        'media': [
          {
            'field': 'signature',
            'key': sigKey,
            'filename': 'signature.png',
            'contentType': 'image/png',
            'blobRef': null,
          },
          {
            'field': 'photo',
            'key': photoKey,
            'filename': 'delivery.jpg',
            'contentType': 'image/jpeg',
            'blobRef': null,
          },
        ],
        'body': {
          'lines': [for (final l in lines) l.toJson()],
          'otp_code': otpCode,
          'proof_of_delivery': {
            'gps_lat': gpsLat,
            'gps_lng': gpsLng,
            'payment_method': paymentMethod,
            'amount_collected': amountCollected,
          },
        },
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
    orderApi: ref.watch(orderApiProvider),
    connectivity: ref.watch(connectivityMonitorProvider),
    mediaStore: ref.watch(mediaStoreProvider),
  ),
);
