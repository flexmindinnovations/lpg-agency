import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:sync_engine/sync_engine.dart';

List<int> _key(int seed) => List<int>.generate(32, (i) => (i + seed) % 256);

void main() {
  late Directory dir;
  late FileMediaStore files;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('enc_media_');
    files = FileMediaStore(dir);
  });

  tearDown(() => dir.deleteSync(recursive: true));

  EncryptedMediaStore store([int seed = 1]) =>
      EncryptedMediaStore(files, loadKey: () async => _key(seed));

  final secret = Uint8List.fromList(
    List<int>.generate(2000, (i) => 65 + (i % 26)), // a recognisable pattern
  );

  test('a file round-trips', () async {
    await store().write('pod/a/photo.jpg', secret);

    expect(await store().read('pod/a/photo.jpg'), secret);
  });

  test('what is on disk is not the photo', () async {
    await store().write('pod/a/photo.jpg', secret);

    final raw = await File(p.join(dir.path, 'pod/a/photo.jpg')).readAsBytes();

    expect(raw, isNot(secret));
    final asText = String.fromCharCodes(raw);
    expect(asText.contains('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), isFalse);
  });

  test('two writes of the same bytes differ on disk (fresh nonce)', () async {
    await store().write('a', secret);
    await store().write('b', secret);

    expect(
      await File(p.join(dir.path, 'a')).readAsBytes(),
      isNot(await File(p.join(dir.path, 'b')).readAsBytes()),
    );
  });

  test('a wrong key cannot read it', () async {
    await store(1).write('a', secret);

    await expectLater(store(2).read('a'), throwsA(anything));
  });

  test('a tampered file is rejected, not returned as garbage', () async {
    await store().write('a', secret);
    final file = File(p.join(dir.path, 'a'));
    final bytes = await file.readAsBytes();
    bytes[bytes.length ~/ 2] ^= 0xff;
    await file.writeAsBytes(bytes);

    await expectLater(store().read('a'), throwsA(anything));
  });

  test('a plain file from before encryption still reads, so an unsent '
      'delivery is not stranded by the upgrade', () async {
    await files.write('pod/old/signature.png', [137, 80, 78, 71, 1, 2, 3]);

    expect(await store().read('pod/old/signature.png'), [
      137,
      80,
      78,
      71,
      1,
      2,
      3,
    ]);
  });

  test('delete, exists and list pass through', () async {
    await store().write('pod/a/photo.jpg', secret);

    expect(await store().exists('pod/a/photo.jpg'), isTrue);
    expect((await store().list()).map((m) => m.key), ['pod/a/photo.jpg']);

    await store().delete('pod/a/photo.jpg');
    expect(await store().exists('pod/a/photo.jpg'), isFalse);
  });

  test('the key is loaded once', () async {
    var loads = 0;
    final s = EncryptedMediaStore(
      files,
      loadKey: () async {
        loads++;
        return _key(1);
      },
    );

    await s.write('a', secret);
    await s.read('a');
    await s.write('b', secret);

    expect(loads, 1);
  });
}
