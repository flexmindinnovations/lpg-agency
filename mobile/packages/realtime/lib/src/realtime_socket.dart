import 'dart:async';

import 'package:web_socket_channel/web_socket_channel.dart';

/// Thin interface over a live socket connection — the seam that makes
/// [RealtimeClient]'s reconnect and subscription-routing logic unit
/// testable without a live WebSocket server. [RealtimeClient] never touches
/// `WebSocketChannel` directly.
abstract interface class RealtimeSocket {
  Stream<dynamic> get stream;
  void send(String message);
  Future<void> close();

  /// The close code the server sent, once the stream is done (`1008`: the
  /// token was rejected). `null` while open or when the connection dropped
  /// without a close frame.
  int? get closeCode;
}

final class _WebSocketChannelSocket implements RealtimeSocket {
  _WebSocketChannelSocket(this._channel) {
    // A connection that cannot be made fails `ready` as well as the stream.
    // The client already handles the stream's error and reconnects; with no
    // listener on `ready` the same failure escapes as an unhandled exception.
    unawaited(_channel.ready.then<void>((_) {}, onError: (Object _) {}));
  }

  final WebSocketChannel _channel;

  @override
  Stream<dynamic> get stream => _channel.stream;

  @override
  void send(String message) => _channel.sink.add(message);

  @override
  Future<void> close() => _channel.sink.close();

  @override
  int? get closeCode => _channel.closeCode;
}

/// The real connection factory — opens an actual WebSocket to [uri].
RealtimeSocket connectRealtimeSocket(Uri uri) =>
    _WebSocketChannelSocket(WebSocketChannel.connect(uri));
