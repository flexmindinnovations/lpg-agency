import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

/// Local storage for proof-of-delivery media (signature, photo) captured
/// offline, before it can be uploaded. Keys are relative paths like
/// `pod/<uuid>/signature.png`.
///
/// An interface so tests use an in-memory fake; the app uses
/// [FileMediaStore] rooted at the app-support directory.
abstract interface class MediaStore {
  Future<void> write(String key, List<int> bytes);
  Future<Uint8List> read(String key);
  Future<void> delete(String key);
  Future<bool> exists(String key);
}

/// [MediaStore] backed by files under [rootDir].
class FileMediaStore implements MediaStore {
  FileMediaStore(this.rootDir);

  final Directory rootDir;

  File _file(String key) => File(p.join(rootDir.path, key));

  @override
  Future<void> write(String key, List<int> bytes) async {
    final file = _file(key);
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
  }

  @override
  Future<Uint8List> read(String key) => _file(key).readAsBytes();

  @override
  Future<void> delete(String key) async {
    final file = _file(key);
    if (await file.exists()) await file.delete();
    // Tidy the now-empty per-delivery folder, ignoring races.
    try {
      final dir = file.parent;
      if (await dir.exists() && await dir.list().isEmpty) {
        await dir.delete();
      }
    } catch (_) {}
  }

  @override
  Future<bool> exists(String key) => _file(key).exists();
}
