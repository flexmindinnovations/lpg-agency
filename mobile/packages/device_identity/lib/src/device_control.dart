import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart';

import 'device_access.dart';
import 'device_api.dart';
import 'device_details.dart';
import 'device_identity.dart';
import 'device_interceptor.dart';
import 'install_id_store.dart';

/// The routes the device-control screens live on.
abstract final class DeviceRoutes {
  static const name = '/name-this-phone';
  static const waiting = '/waiting-for-approval';
  static const blocked = '/phone-blocked';

  static const all = {name, waiting, blocked};
}

/// Everything an app needs for device control, in one object (ADR-071): the
/// phone's [identity], the [access] state, and the router redirect that
/// shows the right screen.
///
/// `main()` calls [setUp] once, after creating the `ApiClient`; the app then
/// merges this into its router's `refreshListenable` and calls [redirect]
/// first in its `redirect`. A [ChangeNotifier] so the router re-evaluates the
/// moment the access state or the "name this phone" step changes.
class DeviceControl extends ChangeNotifier with WidgetsBindingObserver {
  DeviceControl({required this.identity, required this.access}) {
    access.addListener(notifyListeners);
  }

  /// Loads the phone's identity and plugs device control into [dio]: every
  /// request then carries the install ID, and a `DEVICE_*` refusal updates
  /// [access].
  ///
  /// [onBlocked] signs the user out when the phone is blocked (their unsent
  /// work stays on the phone); [onResumed] runs when a waiting or blocked
  /// phone is allowed again (the Driver app sends its saved deliveries).
  static Future<DeviceControl> setUp({
    required Dio dio,
    required String appType,
    required Future<void> Function() onBlocked,
    void Function()? onResumed,
    DeviceIdentityStorage? storage,
    DeviceDetailsSourceFactory? detailsSource,
  }) async {
    final identity = await DeviceIdentity.load(
      appType: appType,
      storage: storage ?? SecureDeviceIdentityStorage(),
      detailsSource: detailsSource?.call() ?? const PluginDeviceDetailsSource(),
    );
    final access = DeviceAccessController(
      api: DeviceApi(dio),
      onBlocked: onBlocked,
      onResumed: onResumed,
    );
    dio.interceptors.insert(
      0,
      DeviceInterceptor(identity: identity, onRefused: access.reportRefusal),
    );
    return DeviceControl(identity: identity, access: access);
  }

  final DeviceIdentity identity;
  final DeviceAccessController access;

  bool _wasAuthenticated = false;

  /// Starts following the session and the app's lifecycle:
  /// - when the user signs in, asks the server where the phone stands (so a
  ///   waiting phone goes straight to its screen);
  /// - when the user signs out of a waiting phone, forgets the waiting state;
  /// - when the app comes back to the foreground, asks again (covers a block
  ///   or an approval that arrived while the app was closed).
  void followSession({
    required Listenable session,
    required bool Function() isAuthenticated,
  }) {
    void onSession() {
      final authenticated = isAuthenticated();
      if (authenticated && !_wasAuthenticated) {
        unawaited(_onSignedIn());
      }
      if (!authenticated &&
          _wasAuthenticated &&
          access.access == DeviceAccess.pending) {
        access.reset();
      }
      _wasAuthenticated = authenticated;
    }

    _wasAuthenticated = isAuthenticated();
    if (_wasAuthenticated) unawaited(access.refresh());
    session.addListener(onSession);
    WidgetsBinding.instance.addObserver(this);
  }

  Future<void> _onSignedIn() async {
    // A session that began before this version asked for a name keeps the
    // model as its name rather than interrupting the user later.
    if (identity.needsName) await identity.saveName(identity.suggestedName);
    notifyListeners();
    await access.refresh();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _wasAuthenticated) {
      unawaited(access.refresh());
    }
  }

  /// Saves the name the user chose; the router then moves on to sign-in.
  Future<void> saveName(String name) async {
    await identity.saveName(name);
    notifyListeners();
  }

  /// Leaves the blocked screen so the user can try signing in again; the
  /// server refuses a phone that is still blocked.
  void tryAgain() => access.reset();

  /// The route the device state calls for, or `null` to carry on with the
  /// app's own redirect. Call it first, once the session is known.
  String? redirect({required String location, required bool authenticated}) {
    final target = switch (access.access) {
      DeviceAccess.blocked => DeviceRoutes.blocked,
      DeviceAccess.pending when authenticated => DeviceRoutes.waiting,
      _ when !authenticated && identity.needsName => DeviceRoutes.name,
      _ => null,
    };
    if (target != null) return target == location ? null : target;
    // Nothing holds the phone back: leave a device screen that no longer
    // applies, and let the app's own redirect pick the destination.
    return DeviceRoutes.all.contains(location) ? '/' : null;
  }

  @override
  void dispose() {
    access.removeListener(notifyListeners);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

/// Lets tests supply a fake [DeviceDetailsSource] to [DeviceControl.setUp].
typedef DeviceDetailsSourceFactory = DeviceDetailsSource Function();
