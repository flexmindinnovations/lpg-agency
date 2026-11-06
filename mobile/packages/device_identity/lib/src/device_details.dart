import 'dart:io' show Platform;

import 'package:android_id/android_id.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';

/// What the app reports about its phone. Only these fields are collected
/// (ADR-071, DPDP): the phone's maker, model and OS, the app's version, the
/// platform, and one supporting hardware identifier (the Android ID / iOS
/// vendor ID, which the server stores only as a one-way hash).
///
/// IMEI and serial numbers cannot be read by normal apps on Android 10 and
/// later, and never on iOS, so they are not collected; the agency can type
/// one as a note in the dashboard.
class DeviceDetails {
  const DeviceDetails({
    this.manufacturer,
    this.model,
    this.osVersion,
    this.appVersion,
    this.platform,
    this.hardwareId,
  });

  final String? manufacturer;
  final String? model;
  final String? osVersion;
  final String? appVersion;

  /// `android` or `ios`.
  final String? platform;

  /// Android ID / iOS vendor ID.
  final String? hardwareId;

  /// The `device` object the sign-in, OTP-verify and refresh bodies carry.
  /// Values are trimmed to the lengths the API accepts; empty ones left out.
  Map<String, dynamic> toJson({String? name}) {
    final json = <String, dynamic>{
      'name': _clip(name, 60),
      'manufacturer': _clip(manufacturer, 100),
      'model': _clip(model, 100),
      'os_version': _clip(osVersion, 50),
      'app_version': _clip(appVersion, 50),
      'platform': _clip(platform, 20),
      'hardware_id': _clip(hardwareId, 128),
    };
    json.removeWhere((_, value) => value == null);
    return json;
  }
}

String? _clip(String? value, int max) {
  final trimmed = value?.trim();
  if (trimmed == null || trimmed.isEmpty) return null;
  return trimmed.length <= max ? trimmed : trimmed.substring(0, max);
}

/// Reads the phone's details. A seam so tests (and platforms the plugins do
/// not cover) never touch a platform channel.
abstract interface class DeviceDetailsSource {
  Future<DeviceDetails> read();
}

/// The real source: `device_info_plus`, `package_info_plus` and `android_id`.
/// Each lookup is isolated — a plugin that fails leaves its fields empty
/// rather than stopping the app from registering.
final class PluginDeviceDetailsSource implements DeviceDetailsSource {
  const PluginDeviceDetailsSource();

  @override
  Future<DeviceDetails> read() async {
    String? appVersion;
    try {
      appVersion = (await PackageInfo.fromPlatform()).version;
    } catch (_) {
      appVersion = null;
    }

    try {
      final plugin = DeviceInfoPlugin();
      if (Platform.isAndroid) {
        final info = await plugin.androidInfo;
        String? androidId;
        try {
          androidId = await const AndroidId().getId();
        } catch (_) {
          androidId = null;
        }
        return DeviceDetails(
          manufacturer: info.manufacturer,
          model: info.model,
          osVersion: 'Android ${info.version.release}',
          appVersion: appVersion,
          platform: 'android',
          hardwareId: androidId,
        );
      }
      if (Platform.isIOS) {
        final info = await plugin.iosInfo;
        return DeviceDetails(
          manufacturer: 'Apple',
          model: info.modelName,
          osVersion: 'iOS ${info.systemVersion}',
          appVersion: appVersion,
          platform: 'ios',
          hardwareId: info.identifierForVendor,
        );
      }
    } catch (_) {
      // Fall through: report what we know.
    }
    return DeviceDetails(appVersion: appVersion);
  }
}
