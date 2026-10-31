import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:realtime/realtime.dart';

void main() {
  test('a connection that cannot be made reports no unhandled error', () async {
    final uncaught = <Object>[];
    final streamErrors = <Object>[];
    final done = Completer<void>();

    await runZonedGuarded(() async {
      // Nothing listens on port 1, so the connection is refused.
      final socket = connectRealtimeSocket(Uri.parse('ws://127.0.0.1:1/ws'));
      socket.stream.listen(
        (_) {},
        onError: streamErrors.add,
        onDone: () {
          if (!done.isCompleted) done.complete();
        },
      );
      await done.future.timeout(const Duration(seconds: 5));
      // Give any stray asynchronous error time to surface.
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }, (error, _) => uncaught.add(error));

    // The stream reports the failure (the client reconnects on it); nothing
    // else escapes.
    expect(streamErrors, isNotEmpty);
    expect(uncaught, isEmpty);
  });
}
