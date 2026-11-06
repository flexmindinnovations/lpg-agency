// The private constructor takes `storage` / `savedName` and assigns the
// private fields; an initializing formal cannot, because a named parameter
// cannot start with an underscore.
// ignore_for_file: prefer_initializing_formals

import 'dart:math';

import 'device_details.dart';
import 'install_id_store.dart';

/// Header carrying the install ID on every request.
const deviceIdHeader = 'X-Device-Id';

/// Header saying which app this is (`driver_app` or `admin_app`).
const appTypeHeader = 'X-App-Type';

/// Who this phone is, to the agency (ADR-071): its install ID, which app is
/// running on it, what it reports about itself, and the name the user gave it.
///
/// The install ID is created the first time the app runs and then never
/// changes. Treat it as a credential: it is sent only in [headers], never
/// logged, and the server keeps just a hash of it.
final class DeviceIdentity {
  DeviceIdentity._({
    required this.installId,
    required this.appType,
    required this.details,
    required DeviceIdentityStorage storage,
    required String? savedName,
  }) : _storage = storage,
       _savedName = savedName;

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
      storage: storage,
      savedName: _blankToNull(await storage.readName()),
    );
  }

  final String installId;

  /// `driver_app` or `admin_app`.
  final String appType;
  final DeviceDetails details;
  final DeviceIdentityStorage _storage;
  String? _savedName;

  /// The name the user gave this phone, or `null` before they have.
  String? get savedName => _savedName;

  /// Whether the user still has to name the phone (first run).
  bool get needsName => _savedName == null;

  /// What the name field starts with: the model, else a plain fallback.
  String get suggestedName => _blankToNull(details.model) ?? 'This phone';

  /// The name sent to the agency: the user's, else the model.
  String get name => _savedName ?? suggestedName;

  Future<void> saveName(String value) async {
    final cleaned = value.trim();
    if (cleaned.isEmpty) return;
    await _storage.writeName(cleaned);
    _savedName = cleaned;
  }

  /// Headers every request to the API carries.
  Map<String, String> get headers => {
    deviceIdHeader: installId,
    appTypeHeader: appType,
  };

  /// The `device` object for the sign-in, OTP-verify and refresh bodies.
  Map<String, dynamic> get authBody => details.toJson(name: name);

  @override
  String toString() => 'DeviceIdentity($appType)'; // never the install ID
}

String? _blankToNull(String? value) {
  final trimmed = value?.trim();
  return (trimmed == null || trimmed.isEmpty) ? null : trimmed;
}
