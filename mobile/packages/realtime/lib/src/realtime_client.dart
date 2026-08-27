// The public constructor parameters below (`wsBaseUrl`, `getAccessToken`)
// are deliberately named without the private fields' leading underscore —
// an initializing formal's named-parameter label is the field name itself,
// and a private label can't be supplied from callers in another library
// (every real caller of this constructor lives in another package).
// ignore_for_file: prefer_initializing_formals

import 'dart:async';
import 'dart:convert';

import 'realtime_socket.dart';

/// Reconnect backoff schedule — mirrors the backend's own `RedisSubscriber`
/// backoff shape (`infrastructure/realtime/subscriber.py`: initial 1s, x2
/// factor, capped at 30s), so a flaky connection degrades the same way on
/// both ends.
const _initialBackoff = Duration(seconds: 1);
const _maxBackoff = Duration(seconds: 30);

/// Wraps the backend's single multiplexed `/ws` WebSocket
/// (`backend/src/lpg/api/v1/routers/ws.py`) behind typed per-topic streams.
/// One physical connection carries every subscription: [subscribeToOrder]
/// and [subscribeToNotifications] each add a server-side "subscribe" intent
/// over that shared connection and filter the inbound message stream by the
/// `type` field the backend's `realtime_handlers.py` puts on every message
/// (`order.status_changed`, `notification.new`).
///
/// Reconnects with exponential backoff on drop, and — because the server
/// forgets a dropped connection's subscriptions (`ConnectionManager
/// .disconnect` clears them) — replays every active intent once the new
/// connection is open.
final class RealtimeClient {
  RealtimeClient({
    required String wsBaseUrl,
    required String? Function() getAccessToken,
    RealtimeSocket Function(Uri uri)? connect,
  }) : _wsBaseUrl = wsBaseUrl,
       _getAccessToken = getAccessToken,
       _connect = connect ?? connectRealtimeSocket;

  final String _wsBaseUrl;
  final String? Function() _getAccessToken;
  final RealtimeSocket Function(Uri uri) _connect;

  RealtimeSocket? _socket;
  StreamSubscription<dynamic>? _socketSubscription;
  final _messages = StreamController<Map<String, dynamic>>.broadcast();
  final Set<String> _activeIntents = {};
  Duration _backoff = _initialBackoff;
  Timer? _reconnectTimer;
  bool _closed = false;

  /// Opens the connection and replays any subscriptions already requested.
  /// [subscribeToOrder]/[subscribeToNotifications] call this automatically
  /// on first use — most callers never need to call it directly.
  Future<void> connect() async {
    if (_socket != null || _closed) return;
    _reconnectTimer?.cancel();

    final token = _getAccessToken();
    final uri = Uri.parse(
      '$_wsBaseUrl/ws',
    ).replace(queryParameters: {'token': ?token});

    final socket = _connect(uri);
    _socket = socket;
    _socketSubscription = socket.stream.listen(
      _handleRawMessage,
      onDone: _handleDisconnect,
      onError: (Object _, StackTrace _) => _handleDisconnect(),
    );

    if (_activeIntents.isNotEmpty) {
      _sendSubscribe(_activeIntents);
    }
  }

  /// Closes the connection permanently — no further reconnect attempts.
  Future<void> disconnect() async {
    _closed = true;
    _reconnectTimer?.cancel();
    await _socketSubscription?.cancel();
    await _socket?.close();
    _socket = null;
  }

  /// Live status-change events for one order — confirmed, assigned, out for
  /// delivery, delivered — the backend's `order.status_changed` messages on
  /// the `order:{orderId}` channel.
  Stream<Map<String, dynamic>> subscribeToOrder(String orderId) {
    _addIntent('order:$orderId');
    return _messages.stream.where(
      (m) => m['type'] == 'order.status_changed' && m['order_id'] == orderId,
    );
  }

  /// New in-app notifications for the signed-in user — the backend's
  /// `notification.new` messages on the per-user `notifications` channel.
  Stream<Map<String, dynamic>> subscribeToNotifications() {
    _addIntent('notifications');
    return _messages.stream.where((m) => m['type'] == 'notification.new');
  }

  void _addIntent(String intent) {
    if (!_activeIntents.add(intent)) return;
    if (_socket == null) {
      unawaited(connect());
    } else {
      _sendSubscribe({intent});
    }
  }

  void _sendSubscribe(Set<String> intents) {
    _socket?.send(jsonEncode({'subscribe': intents.toList()}));
  }

  void _handleRawMessage(dynamic raw) {
    if (raw is! String) return;
    final Map<String, dynamic> data;
    try {
      data = jsonDecode(raw) as Map<String, dynamic>;
    } on FormatException {
      return;
    }

    // Any message — including the server's own idle-keepalive ping — is
    // proof the connection is healthy, so this is where backoff resets.
    // Resetting it in `connect()` instead would mean a server that accepts
    // the socket and then immediately drops it (mid-outage) gets hammered
    // at a constant 1s interval forever, never actually backing off.
    _backoff = _initialBackoff;

    if (data['type'] == 'ping') {
      _socket?.send(jsonEncode({'type': 'pong'}));
      return;
    }
    _messages.add(data);
  }

  void _handleDisconnect() {
    if (_socket == null) return; // already handled
    unawaited(_socketSubscription?.cancel());
    _socketSubscription = null;
    _socket = null;
    if (_closed) return;

    _reconnectTimer = Timer(_backoff, connect);
    final doubled = _backoff * 2;
    _backoff = doubled > _maxBackoff ? _maxBackoff : doubled;
  }
}
