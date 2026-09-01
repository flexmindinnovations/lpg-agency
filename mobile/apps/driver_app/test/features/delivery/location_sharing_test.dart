import 'dart:async';
import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';

void main() {
  group('LocationThrottle', () {
    test('accepts the first reading', () {
      final throttle = LocationThrottle();
      expect(throttle.accept(DateTime(2026, 9, 1, 12, 0, 0)), isTrue);
    });

    test('rejects a second reading inside the minimum interval', () {
      final throttle = LocationThrottle(
        minInterval: const Duration(seconds: 15),
      );
      final t0 = DateTime(2026, 9, 1, 12, 0, 0);

      expect(throttle.accept(t0), isTrue);
      expect(throttle.accept(t0.add(const Duration(seconds: 5))), isFalse);
      expect(throttle.accept(t0.add(const Duration(seconds: 14))), isFalse);
    });

    test('accepts again once the interval has elapsed', () {
      final throttle = LocationThrottle(
        minInterval: const Duration(seconds: 15),
      );
      final t0 = DateTime(2026, 9, 1, 12, 0, 0);

      expect(throttle.accept(t0), isTrue);
      expect(throttle.accept(t0.add(const Duration(seconds: 15))), isTrue);
      // ...and the window then restarts from that accepted reading.
      expect(throttle.accept(t0.add(const Duration(seconds: 20))), isFalse);
    });
  });

  group('buildRouteLocationSettings', () {
    tearDown(() => debugDefaultTargetPlatformOverride = null);

    test('Android gets a foreground-service notification', () {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      final settings = buildRouteLocationSettings();

      expect(settings, isA<AndroidSettings>());
      final android = settings as AndroidSettings;
      expect(android.foregroundNotificationConfig, isNotNull);
      expect(android.foregroundNotificationConfig!.setOngoing, isTrue);
      expect(android.foregroundNotificationConfig!.enableWakeLock, isTrue);
    });

    test('iOS opts into background location updates', () {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      final settings = buildRouteLocationSettings();

      expect(settings, isA<AppleSettings>());
      final apple = settings as AppleSettings;
      expect(apple.allowBackgroundLocationUpdates, isTrue);
      expect(apple.pauseLocationUpdatesAutomatically, isFalse);
      expect(apple.activityType, ActivityType.automotiveNavigation);
    });

    test('other platforms fall back to plain settings', () {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      final settings = buildRouteLocationSettings();

      expect(settings, isA<LocationSettings>());
      expect(settings, isNot(isA<AndroidSettings>()));
      expect(settings, isNot(isA<AppleSettings>()));
    });
  });

  group('LocationSharingController', () {
    Position fix() => Position(
      latitude: 17.44,
      longitude: 78.35,
      timestamp: DateTime(2026, 9, 1),
      accuracy: 5,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 10,
      headingAccuracy: 0,
      speed: 4,
      speedAccuracy: 0,
    );

    test('reports a fix while the route is in progress', () async {
      final adapter = _StubAdapter((_) => _empty(204));
      final controller = LocationSharingController(
        routeApi: RouteApi(_dio(adapter)),
        geolocator: _FakeGeolocator([fix()]),
      );
      addTearDown(controller.dispose);

      await controller.start('route-1');
      await Future<void>.delayed(const Duration(milliseconds: 20));

      expect(adapter.paths, ['/api/v1/routes/route-1/location']);
      expect(controller.state.status, LocationSharingStatus.sharing);
    });

    test(
      'stops sharing when the backend says the route is not active',
      () async {
        final adapter = _StubAdapter(
          (_) => _json({
            'error_code': 'CONFLICT',
            'detail': 'route not active',
          }, 409),
        );
        final controller = LocationSharingController(
          routeApi: RouteApi(_dio(adapter)),
          geolocator: _FakeGeolocator([fix()]),
        );
        addTearDown(controller.dispose);

        final seen = <LocationSharingStatus>[];
        final sub = controller.states.listen((s) => seen.add(s.status));

        await controller.start('route-1');
        await Future<void>.delayed(const Duration(milliseconds: 20));
        await sub.cancel();

        expect(controller.state.status, LocationSharingStatus.off);
        expect(controller.state.message, contains('no longer active'));
        expect(seen, contains(LocationSharingStatus.off));
      },
    );
  });
}

Dio _dio(HttpClientAdapter adapter) =>
    Dio(BaseOptions(baseUrl: 'https://api.test'))..httpClientAdapter = adapter;

ResponseBody _empty(int status) => ResponseBody.fromString('', status);

ResponseBody _json(Map<String, dynamic> body, int status) =>
    ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this._handler);

  final ResponseBody Function(RequestOptions options) _handler;
  final paths = <String>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    paths.add(options.path);
    return _handler(options);
  }

  @override
  void close({bool force = false}) {}
}

class _FakeGeolocator extends DriverGeolocator {
  _FakeGeolocator(this._fixes);

  final List<Position> _fixes;

  @override
  Future<LocationPermission> ensurePermission() async =>
      LocationPermission.whileInUse;

  @override
  Stream<Position> positions() => Stream.fromIterable(_fixes);
}
