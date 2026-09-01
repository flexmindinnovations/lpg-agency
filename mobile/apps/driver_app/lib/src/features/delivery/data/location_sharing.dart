import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../../../api_provider.dart';

/// Location settings for continuous route sharing.
///
/// On Android this attaches a foreground-service notification so updates keep
/// flowing while the app is backgrounded or the screen is off; on iOS it opts
/// into background location updates. Other platforms (and the widget tester)
/// fall back to plain [LocationSettings].
LocationSettings buildRouteLocationSettings() {
  const accuracy = LocationAccuracy.high;
  const distanceFilter = 25;
  switch (defaultTargetPlatform) {
    case TargetPlatform.android:
      return AndroidSettings(
        accuracy: accuracy,
        distanceFilter: distanceFilter,
        intervalDuration: const Duration(seconds: 15),
        foregroundNotificationConfig: const ForegroundNotificationConfig(
          notificationTitle: 'Sharing your delivery location',
          notificationText: 'Customers on your route can see where you are.',
          notificationChannelName: 'Delivery location sharing',
          enableWakeLock: true,
          setOngoing: true,
        ),
      );
    case TargetPlatform.iOS:
      return AppleSettings(
        accuracy: accuracy,
        distanceFilter: distanceFilter,
        activityType: ActivityType.automotiveNavigation,
        pauseLocationUpdatesAutomatically: false,
        showBackgroundLocationIndicator: true,
        allowBackgroundLocationUpdates: true,
      );
    default:
      return const LocationSettings(
        accuracy: accuracy,
        distanceFilter: distanceFilter,
      );
  }
}

/// Rate-limits location POSTs. `geolocator`'s position stream fires on
/// movement (a distance filter), which can be far more often than every
/// 15s in a moving vehicle — this caps the actual network traffic.
class LocationThrottle {
  LocationThrottle({this.minInterval = const Duration(seconds: 15)});

  final Duration minInterval;
  DateTime? _lastAcceptedAt;

  bool accept(DateTime now) {
    final last = _lastAcceptedAt;
    if (last == null || now.difference(last) >= minInterval) {
      _lastAcceptedAt = now;
      return true;
    }
    return false;
  }
}

enum LocationSharingStatus {
  off,
  requesting,
  sharing,
  permissionBlocked,
  error,
}

class LocationSharingState {
  const LocationSharingState({
    this.status = LocationSharingStatus.off,
    this.lastSentAt,
    this.message,
  });

  final LocationSharingStatus status;
  final DateTime? lastSentAt;
  final String? message;

  bool get isSharing => status == LocationSharingStatus.sharing;

  LocationSharingState copyWith({
    LocationSharingStatus? status,
    DateTime? lastSentAt,
    String? message,
  }) => LocationSharingState(
    status: status ?? this.status,
    lastSentAt: lastSentAt ?? this.lastSentAt,
    message: message,
  );
}

/// Thin wrapper over `geolocator`'s static API so the controller can be
/// tested without the platform channel.
class DriverGeolocator {
  const DriverGeolocator();

  Future<LocationPermission> ensurePermission() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    return permission;
  }

  Stream<Position> positions() => Geolocator.getPositionStream(
    locationSettings: buildRouteLocationSettings(),
  );

  /// A single fix — used to stamp a proof of delivery.
  Future<Position> currentPosition() => Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
  );
}

final driverGeolocatorProvider = Provider<DriverGeolocator>(
  (ref) => const DriverGeolocator(),
);

/// Location sharing for the current delivery route. The driver turns it on
/// from the Active Delivery screen; from then on it is driven by
/// [buildRouteLocationSettings] — an Android foreground service (persistent
/// notification) / iOS background updates — so it keeps reporting when the
/// driver navigates to a stop, backgrounds the app, or locks the screen. It
/// stops on the manual toggle, when the route is no longer `in_progress`
/// (the backend answers `409`), or when the app process is torn down.
class LocationSharingController {
  LocationSharingController({required this.routeApi, required this.geolocator});

  final RouteApi routeApi;
  final DriverGeolocator geolocator;
  final _throttle = LocationThrottle();
  final _states = StreamController<LocationSharingState>.broadcast();

  StreamSubscription<Position>? _sub;
  LocationSharingState _state = const LocationSharingState();

  LocationSharingState get state => _state;

  /// Emits the current state immediately, then every change.
  Stream<LocationSharingState> get states async* {
    yield _state;
    yield* _states.stream;
  }

  void _emit(LocationSharingState next) {
    _state = next;
    if (!_states.isClosed) _states.add(next);
  }

  Future<void> start(String routeId) async {
    if (_state.isSharing) return;
    _emit(_state.copyWith(status: LocationSharingStatus.requesting));

    final permission = await geolocator.ensurePermission();
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      _emit(
        const LocationSharingState(
          status: LocationSharingStatus.permissionBlocked,
          message: 'Location permission is needed to share your position.',
        ),
      );
      return;
    }

    _emit(const LocationSharingState(status: LocationSharingStatus.sharing));
    _sub = geolocator.positions().listen(
      (position) => _report(routeId, position),
    );
  }

  void stop() {
    _sub?.cancel();
    _sub = null;
    if (_state.status != LocationSharingStatus.off) {
      _emit(
        LocationSharingState(
          status: LocationSharingStatus.off,
          lastSentAt: _state.lastSentAt,
        ),
      );
    }
  }

  Future<void> _report(String routeId, Position position) async {
    if (!_throttle.accept(DateTime.now())) return;

    final result = await routeApi.reportLocation(
      routeId,
      DriverLocationReport(
        latitude: position.latitude,
        longitude: position.longitude,
        heading: position.heading >= 0 ? position.heading : null,
        speedKph: position.speed >= 0 ? position.speed * 3.6 : null,
        accuracyM: position.accuracy >= 0 ? position.accuracy : null,
      ),
    );

    result.when(
      onSuccess: (_) => _emit(
        LocationSharingState(
          status: LocationSharingStatus.sharing,
          lastSentAt: DateTime.now(),
        ),
      ),
      onFailure: (failure) {
        // The route has ended (or isn't in progress) — nothing more to share.
        if (failure.errorCode == 'CONFLICT') {
          stop();
          _emit(
            LocationSharingState(
              status: LocationSharingStatus.off,
              lastSentAt: _state.lastSentAt,
              message: 'Sharing stopped — this route is no longer active.',
            ),
          );
          return;
        }
        _emit(
          _state.copyWith(
            status: LocationSharingStatus.sharing,
            message: failure.message,
          ),
        );
      },
    );
  }

  void dispose() {
    _sub?.cancel();
    _states.close();
  }
}

/// Kept alive for the whole session (not `autoDispose`) on purpose: sharing
/// must outlive the Active Delivery screen that starts it.
final locationSharingControllerProvider = Provider<LocationSharingController>((
  ref,
) {
  final controller = LocationSharingController(
    routeApi: ref.watch(routeApiProvider),
    geolocator: ref.watch(driverGeolocatorProvider),
  );
  ref.onDispose(controller.dispose);
  return controller;
});

final locationSharingStateProvider = StreamProvider<LocationSharingState>(
  (ref) => ref.watch(locationSharingControllerProvider).states,
);
