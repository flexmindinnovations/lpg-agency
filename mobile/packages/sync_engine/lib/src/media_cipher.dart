import 'dart:isolate';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

/// Seals and opens proof-of-delivery files with AES-256-GCM. Sealed bytes are
/// `nonce (12) + ciphertext + tag (16)`, the same layout from every
/// implementation, so a file sealed by one opens with any other.
abstract interface class MediaCipher {
  Future<Uint8List> encrypt(List<int> plain, List<int> key);
  Future<Uint8List> decrypt(List<int> sealed, List<int> key);
}

Future<Uint8List> _seal(List<int> plain, List<int> key) async {
  final box = await AesGcm.with256bits().encrypt(
    plain,
    secretKey: SecretKey(key),
  );
  return Uint8List.fromList(box.concatenation());
}

Future<Uint8List> _open(List<int> sealed, List<int> key) async {
  final box = SecretBox.fromConcatenation(
    sealed,
    nonceLength: 12,
    macLength: 16,
  );
  return Uint8List.fromList(
    await AesGcm.with256bits().decrypt(box, secretKey: SecretKey(key)),
  );
}

/// Whatever AES-GCM the `cryptography` package is currently set to use, run
/// on the calling isolate. With `cryptography_flutter` on Android or iOS that
/// is the phone's own AES (off the UI thread); without it, it is pure Dart and
/// **blocks the isolate it runs on** (about 6 to 8 MB/s on a server core, so a
/// 3 MB photo takes roughly half a second there and longer on a phone). Use it
/// only where native AES is known to be active, behind a [FallbackMediaCipher].
class InProcessMediaCipher implements MediaCipher {
  const InProcessMediaCipher();

  @override
  Future<Uint8List> encrypt(List<int> plain, List<int> key) =>
      _seal(plain, key);

  @override
  Future<Uint8List> decrypt(List<int> sealed, List<int> key) =>
      _open(sealed, key);
}

/// Pure-Dart AES-GCM on a **background isolate**: the app stays responsive
/// while a large photo is sealed or opened. It is no faster, only off the UI
/// thread, and costs one copy of the bytes each way. The default everywhere
/// native AES is not available (desktop, tests, the fallback on a phone).
class IsolateMediaCipher implements MediaCipher {
  const IsolateMediaCipher();

  @override
  Future<Uint8List> encrypt(List<int> plain, List<int> key) {
    final data = Uint8List.fromList(plain);
    final secret = Uint8List.fromList(key);
    return Isolate.run(() => _seal(data, secret));
  }

  @override
  Future<Uint8List> decrypt(List<int> sealed, List<int> key) {
    final data = Uint8List.fromList(sealed);
    final secret = Uint8List.fromList(key);
    return Isolate.run(() => _open(data, secret));
  }
}

/// Tries [primary] (native AES) and, if it fails for any reason other than the
/// data being tampered with or the key being wrong, does the same work with
/// [fallback]. After one failure it stops trying [primary] for the rest of the
/// run, so a phone without the native path does not pay for a failed call on
/// every photo.
class FallbackMediaCipher implements MediaCipher {
  FallbackMediaCipher(this.primary, this.fallback);

  final MediaCipher primary;
  final MediaCipher fallback;
  bool _primaryWorks = true;

  @override
  Future<Uint8List> encrypt(List<int> plain, List<int> key) async {
    if (_primaryWorks) {
      try {
        return await primary.encrypt(plain, key);
      } catch (_) {
        _primaryWorks = false;
      }
    }
    return fallback.encrypt(plain, key);
  }

  @override
  Future<Uint8List> decrypt(List<int> sealed, List<int> key) async {
    if (_primaryWorks) {
      try {
        return await primary.decrypt(sealed, key);
      } on SecretBoxAuthenticationError {
        rethrow; // tampered or wrongly keyed: another cipher cannot fix that
      } catch (_) {
        _primaryWorks = false;
      }
    }
    return fallback.decrypt(sealed, key);
  }
}
