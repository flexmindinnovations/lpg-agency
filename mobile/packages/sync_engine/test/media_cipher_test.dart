import 'dart:async';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sync_engine/sync_engine.dart';

final _key = List<int>.generate(32, (i) => i);
final _wrongKey = List<int>.generate(32, (i) => i + 1);
final _plain = Uint8List.fromList(List<int>.generate(5000, (i) => i % 251));

class _Broken implements MediaCipher {
  int calls = 0;

  @override
  Future<Uint8List> encrypt(List<int> plain, List<int> key) async {
    calls++;
    throw StateError('no native AES here');
  }

  @override
  Future<Uint8List> decrypt(List<int> sealed, List<int> key) async {
    calls++;
    throw StateError('no native AES here');
  }
}

void main() {
  group('IsolateMediaCipher', () {
    const cipher = IsolateMediaCipher();

    test('round trips', () async {
      final sealed = await cipher.encrypt(_plain, _key);

      expect(sealed, isNot(_plain));
      expect(await cipher.decrypt(sealed, _key), _plain);
    });

    test('seals the same layout as the in-process cipher, so either opens '
        'what the other sealed', () async {
      const inProcess = InProcessMediaCipher();

      expect(
        await inProcess.decrypt(await cipher.encrypt(_plain, _key), _key),
        _plain,
      );
      expect(
        await cipher.decrypt(await inProcess.encrypt(_plain, _key), _key),
        _plain,
      );
    });

    test('a wrong key or a tampered file is rejected', () async {
      final sealed = await cipher.encrypt(_plain, _key);
      await expectLater(cipher.decrypt(sealed, _wrongKey), throwsA(anything));

      sealed[sealed.length ~/ 2] ^= 0xff;
      await expectLater(cipher.decrypt(sealed, _key), throwsA(anything));
    });

    test(
      'a large photo does not freeze the isolate that asked for it',
      () async {
        // 3 MB: about half a second of pure-Dart AES-GCM on a fast core. Run
        // on the calling isolate that is one long stall; on a background
        // isolate the event loop keeps turning.
        final photo = Uint8List.fromList(
          List<int>.generate(3 * 1024 * 1024, (i) => (i * 31) % 256),
        );
        var worstGap = Duration.zero;
        var last = DateTime.now();
        final ticker = Timer.periodic(const Duration(milliseconds: 5), (_) {
          final now = DateTime.now();
          final gap = now.difference(last);
          if (gap > worstGap) worstGap = gap;
          last = now;
        });

        final stopwatch = Stopwatch()..start();
        await cipher.encrypt(photo, _key);
        stopwatch.stop();
        ticker.cancel();

        expect(
          stopwatch.elapsedMilliseconds,
          greaterThan(150),
          reason: 'the work was real (not skipped)',
        );
        expect(
          worstGap,
          lessThan(const Duration(milliseconds: 120)),
          reason:
              'the event loop stalled for $worstGap during '
              '${stopwatch.elapsedMilliseconds} ms of encryption',
        );
      },
    );
  });

  group('FallbackMediaCipher', () {
    test('uses the primary while it works', () async {
      final primary = const InProcessMediaCipher();
      final cipher = FallbackMediaCipher(primary, _Broken());

      final sealed = await cipher.encrypt(_plain, _key);

      expect(await cipher.decrypt(sealed, _key), _plain);
    });

    test('falls back when the primary fails, and stops asking it', () async {
      final broken = _Broken();
      final cipher = FallbackMediaCipher(broken, const IsolateMediaCipher());

      final sealed = await cipher.encrypt(_plain, _key);
      expect(await cipher.decrypt(sealed, _key), _plain);
      await cipher.encrypt(_plain, _key);

      expect(broken.calls, 1, reason: 'one failed call, then it is skipped');
    });

    test('a tampered file is not retried with another cipher', () async {
      final sealed = await const InProcessMediaCipher().encrypt(_plain, _key);
      sealed[sealed.length ~/ 2] ^= 0xff;
      final fallback = _CountingFallback();
      final cipher = FallbackMediaCipher(
        const InProcessMediaCipher(),
        fallback,
      );

      await expectLater(
        cipher.decrypt(sealed, _key),
        throwsA(isA<SecretBoxAuthenticationError>()),
      );
      expect(fallback.calls, 0);
    });
  });
}

class _CountingFallback implements MediaCipher {
  int calls = 0;

  @override
  Future<Uint8List> encrypt(List<int> plain, List<int> key) async {
    calls++;
    return Uint8List(0);
  }

  @override
  Future<Uint8List> decrypt(List<int> sealed, List<int> key) async {
    calls++;
    return Uint8List(0);
  }
}
