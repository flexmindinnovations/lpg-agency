import 'dart:math';

import 'device_details.dart';
import 'install_id_store.dart';

/// Header carrying the install ID on every request.
const deviceIdHeader = 'X-Device-Id';

/// Header saying which app this is (`driver_app` or `admin_app`).
const appTypeHeader = 'X-App-Type';

/// Who this phone is, to the agency (ADR-071): its install ID, which app is
/// running on it, and what it reports about itself. The phone's *name* lives
/// on the server (one record per phone per agency), not here.
///
/// The install ID is created the first time the app runs and then never
/// changes. Treat it as a credential: it is sent only in [headers], never
/// logged, and the server keeps just a hash of it.
final class DeviceIdentity {
  DeviceIdentity._({
    required this.installId,
    required this.appType,
    required this.details,
  });

  /// Loads the saved identity, creating the install ID on first run.
  static Future<DeviceIdentity> load({
    required String appType,
    required DeviceIdentityStorage storage,
    DeviceDetailsSource detailsSource = const PluginDeviceDetailsSource(),
    Random? random,
  }) async {
    var installId = await storage.readInstallId();
    if (installId == null || installId.isEmpty) {
      installId = generateInstallId(random);
      await storage.writeInstallId(installId);
    }
    return DeviceIdentity._(
      installId: installId,
      appType: appType,
      details: await detailsSource.read(),
    );
  }

  final String installId;

  /// `driver_app` or `admin_app`.
  final String appType;
  final DeviceDetails details;

  /// Headers every request to the API carries.
  Map<String, String> get headers => {
    deviceIdHeader: installId,
    appTypeHeader: appType,
  };

  /// The `device` object for the sign-in, OTP-verify and refresh bodies. It
  /// carries no name: the agency recognises a phone it has seen (by its
  /// hardware code) and names a new one itself, then the app asks the user
  /// once (`GET /devices/me` says `needs_name`).
  Map<String, dynamic> get authBody => details.toJson();

  @override
  String toString() => 'DeviceIdentity($appType)'; // never the install ID
}
