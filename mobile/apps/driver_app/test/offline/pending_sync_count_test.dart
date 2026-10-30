import 'dart:async';

import 'package:driver_app/src/offline/pending_sync.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Lets the stream event and the provider rebuilds it triggers run.
Future<void> _settle(ProviderContainer container) async {
  await Future<void>.delayed(const Duration(milliseconds: 10));
  await container.pump();
  await Future<void>.delayed(const Duration(milliseconds: 10));
}

void main() {
  test('what is read from the server is read again when the queue drains, '
      'and not on every emission', () async {
    final queue = StreamController<Set<String>>();
    addTearDown(queue.close);
    final container = ProviderContainer(
      overrides: [
        pendingSyncAggregatesProvider.overrideWith((ref) => queue.stream),
      ],
    );
    addTearDown(container.dispose);

    // A stand-in for the route, history and cash reads, which all watch the
    // count.
    var reads = 0;
    final serverRead = Provider<int>((ref) {
      ref.watch(pendingSyncCountProvider);
      return ++reads;
    });
    container.listen(serverRead, (_, _) {});
    container.listen(pendingSyncAggregatesProvider, (_, _) {});
    expect(reads, 1);

    // The driver confirms the load: one action is queued.
    queue.add({'route-1'});
    await _settle(container);
    expect(container.read(pendingSyncCountProvider), 1);
    expect(reads, 2);

    // Another emission with the same number waiting changes nothing.
    queue.add({'route-1'});
    await _settle(container);
    expect(reads, 2);

    // The action reaches the server and the queue empties: read again, so
    // the "check your van load" card sees the confirmed route.
    queue.add(<String>{});
    await _settle(container);
    expect(container.read(pendingSyncCountProvider), 0);
    expect(reads, 3);
  });
}
