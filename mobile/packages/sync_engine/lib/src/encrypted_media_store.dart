// The public named parameters cannot be private initializing formals.
// ignore_for_file: prefer_initializing_formals

import 'dart:typed_data';

import 'media_cipher.dart';
import 'media_store.dart';

/// Encrypts everything written to [_inner] (AES-256-GCM, a fresh nonce per
/// file), so proof-of-delivery photos and signatures are not readable from the
/// phone's storage. The database holding the queue is already encrypted; this
/// closes the same gap for the files it points to.
///
/// File layout: a 5-byte marker, then nonce, ciphertext and authentication
/// tag. A file that does not start with the marker is a plain file written
/// before encryption existed; it is read as it is, so an unsent delivery from
/// before the upgrade still uploads, and it is deleted as usual once sent.
/// A tampered or wrongly keyed file fails to read rather than returning
/// garbage.
class EncryptedMediaStore implements MediaStore {
  /// [loadKey] returns 32 secret bytes (kept in secure storage in the app);
  /// it is called once and the result reused. [cipher] defaults to
  /// [IsolateMediaCipher], which keeps the app responsive; the Driver app
  /// passes a native-first cipher on phones.
  EncryptedMediaStore(
    this._inner, {
    required Future<List<int>> Function() loadKey,
    MediaCipher cipher = const IsolateMediaCipher(),
  }) : _loadKey = loadKey,
       _cipher = cipher;

  static const _marker = [0x4c, 0x50, 0x47, 0x4d, 0x31]; // "LPGM1"

  final MediaStore _inner;
  final Future<List<int>> Function() _loadKey;
  final MediaCipher _cipher;
  List<int>? _key;

  Future<List<int>> _secret() async => _key ??= await _loadKey();

  @override
  Future<void> write(String key, List<int> bytes) async {
    final sealed = await _cipher.encrypt(bytes, await _secret());
    await _inner.write(key, [..._marker, ...sealed]);
  }

  @override
  Future<Uint8List> read(String key) async {
    final stored = await _inner.read(key);
    if (!_hasMarker(stored)) return stored; // written before encryption
    return _cipher.decrypt(stored.sublist(_marker.length), await _secret());
  }

  bool _hasMarker(Uint8List bytes) {
    if (bytes.length < _marker.length) return false;
    for (var i = 0; i < _marker.length; i++) {
      if (bytes[i] != _marker[i]) return false;
    }
    return true;
  }

  @override
  Future<void> delete(String key) => _inner.delete(key);

  @override
  Future<bool> exists(String key) => _inner.exists(key);

  @override
  Future<List<StoredMedia>> list() => _inner.list();
}
