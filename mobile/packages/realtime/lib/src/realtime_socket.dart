import 'package:web_socket_channel/web_socket_channel.dart';

/// Thin interface over a live socket connection — the seam that makes
/// [RealtimeClient]'s reconnect and subscription-routing logic unit
/// testable without a live WebSocket server. [RealtimeClient] never touches
/// `WebSocketChannel` directly.
abstract interface class RealtimeSocket {
  Stream<dynamic> get stream;
  void send(String message);
  Future<void> close();
}

final class _WebSocketChannelSocket implements RealtimeSocket {
  _WebSocketChannelSocket(this._channel);

  final WebSocketChannel _channel;

  @override
  Stream<dynamic> get stream => _channel.stream;

  @override
  void send(String message) => _channel.sink.add(message);

  @override
  Future<void> close() => _channel.sink.close();
}

/// The real connection factory — opens an actual WebSocket to [uri].
RealtimeSocket connectRealtimeSocket(Uri uri) =>
    _WebSocketChannelSocket(WebSocketChannel.connect(uri));
