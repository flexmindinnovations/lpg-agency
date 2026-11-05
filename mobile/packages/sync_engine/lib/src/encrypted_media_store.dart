import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

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
  /// it is called once and the result reused.
  EncryptedMediaStore(
    this._inner, {
    required Future<List<int>> Function() loadKey,
  }) : // The public `loadKey` parameter cannot be a private initializing formal.
       // ignore: prefer_initializing_formals
       _loadKey = loadKey;

  static const _marker = [0x4c, 0x50, 0x47, 0x4d, 0x31]; // "LPGM1"
  static final _cipher = AesGcm.with256bits();

  final MediaStore _inner;
  final Future<List<int>> Function() _loadKey;
  SecretKey? _key;

  Future<SecretKey> _secret() async => _key ??= SecretKey(await _loadKey());

  @override
  Future<void> write(String key, List<int> bytes) async {
    final box = await _cipher.encrypt(bytes, secretKey: await _secret());
    await _inner.write(key, [..._marker, ...box.concatenation()]);
  }

  @override
  Future<Uint8List> read(String key) async {
    final stored = await _inner.read(key);
    if (!_hasMarker(stored)) return stored; // written before encryption
    final box = SecretBox.fromConcatenation(
      stored.sublist(_marker.length),
      nonceLength: _cipher.nonceLength,
      macLength: _cipher.macAlgorithm.macLength,
    );
    return Uint8List.fromList(
      await _cipher.decrypt(box, secretKey: await _secret()),
    );
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
