import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _installIdKey = 'device.install_id';
const _deviceNameKey = 'device.name';

Future<void> _defaultWrite(String key, String value) =>
    const FlutterSecureStorage().write(key: key, value: value);

Future<String?> _defaultRead(String key) =>
    const FlutterSecureStorage().read(key: key);

/// Durable storage for this app instance's install ID and the name the user
/// gave the phone.
///
/// The install ID is the access key the agency approves (ADR-071), so it
/// lives in platform secure storage (Keystore / Keychain), exactly like the
/// refresh token. It survives app restarts and updates, and is lost when the
/// app's data is cleared or the app is uninstalled — then the phone shows up
/// as a new one and needs approving again, which is intended.
abstract interface class DeviceIdentityStorage {
  Future<String?> readInstallId();
  Future<void> writeInstallId(String value);
  Future<String?> readName();
  Future<void> writeName(String value);
}

/// [DeviceIdentityStorage] backed by `flutter_secure_storage`. Tests inject
/// in-memory [read]/[write] functions so no platform channel is touched.
final class SecureDeviceIdentityStorage implements DeviceIdentityStorage {
  SecureDeviceIdentityStorage({
    Future<void> Function(String key, String value)? write,
    Future<String?> Function(String key)? read,
  }) : _write = write ?? _defaultWrite,
       _read = read ?? _defaultRead;

  final Future<void> Function(String key, String value) _write;
  final Future<String?> Function(String key) _read;

  @override
  Future<String?> readInstallId() => _read(_installIdKey);

  @override
  Future<void> writeInstallId(String value) => _write(_installIdKey, value);

  @override
  Future<String?> readName() => _read(_deviceNameKey);

  @override
  Future<void> writeName(String value) => _write(_deviceNameKey, value);
}

/// A fresh install ID: 32 random bytes from a cryptographically secure
/// source, as 64 hex characters. Random on purpose — nothing about the phone
/// is derived into it, so it identifies this install and nothing else.
String generateInstallId([Random? random]) {
  final source = random ?? Random.secure();
  final buffer = StringBuffer();
  for (var i = 0; i < 32; i++) {
    buffer.write(source.nextInt(256).toRadixString(16).padLeft(2, '0'));
  }
  return buffer.toString();
}
