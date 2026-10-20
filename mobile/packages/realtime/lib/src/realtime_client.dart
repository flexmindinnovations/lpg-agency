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

/// WebSocket close code the backend uses when it rejects the access token
/// (RFC 6455 1008, "policy violation").
const tokenRejectedCloseCode = 1008;

/// Wraps the backend's single multiplexed `/api/v1/ws` WebSocket
/// (`backend/src/lpg/api/v1/routers/ws.py`) behind typed per-topic streams.
/// One physical connection carries every subscription: each `subscribeTo…`
/// method adds a server-side "subscribe" intent over that shared connection
/// and filters the inbound message stream by the `type` field the backend's
/// `realtime_handlers.py` puts on every message.
///
/// Authentication: the access token is sent as the first frame
/// (`{"type":"auth","token":…}`), never in the URL, so it cannot end up in
/// proxy or server access logs. The server answers `{"type":"ready"}`; only
/// then are subscribe intents sent.
///
/// Reconnects with exponential backoff on drop, and — because the server
/// forgets a dropped connection's subscriptions — replays every active intent
/// once the new connection is ready, then emits on [reconnected] so callers
/// can refetch whatever they may have missed while offline.
final class RealtimeClient {
  RealtimeClient({
    required String wsBaseUrl,
    required String? Function() getAccessToken,
    RealtimeSocket Function(Uri uri)? connect,
    Future<void> Function()? onTokenRejected,
  }) : _wsBaseUrl = wsBaseUrl,
       _getAccessToken = getAccessToken,
       _connect = connect ?? connectRealtimeSocket,
       _onTokenRejected = onTokenRejected;

  final String _wsBaseUrl;
  final String? Function() _getAccessToken;
  final RealtimeSocket Function(Uri uri) _connect;
  final Future<void> Function()? _onTokenRejected;

  RealtimeSocket? _socket;
  StreamSubscription<dynamic>? _socketSubscription;
  final _messages = StreamController<Map<String, dynamic>>.broadcast();
  final _reconnected = StreamController<void>.broadcast();
  final Set<String> _activeIntents = {};
  Duration _backoff = _initialBackoff;
  Timer? _reconnectTimer;
  bool _closed = false;
  bool _paused = false;
  bool _ready = false;
  bool _everReady = false;

  /// Emits each time the connection becomes ready again after a drop (not on
  /// the first connect). Listeners should refetch state that live events
  /// would otherwise have delivered while the socket was down.
  Stream<void> get reconnected => _reconnected.stream;

  /// Opens the connection and replays any subscriptions already requested.
  /// The `subscribeTo…` methods call this automatically on first use — most
  /// callers never need to call it directly.
  Future<void> connect() async {
    if (_socket != null || _closed || _paused) return;
    _reconnectTimer?.cancel();

    final token = _getAccessToken();
    if (token == null || token.isEmpty) {
      // Signed out or token not yet loaded — try again later rather than
      // opening a socket the server will reject.
      _scheduleReconnect();
      return;
    }

    // The backend mounts ws.py's router under its versioned API prefix
    // like every other route — there's no bare `/ws` at the origin root.
    final uri = Uri.parse('$_wsBaseUrl/api/v1/ws');

    final socket = _connect(uri);
    _socket = socket;
    _ready = false;
    _socketSubscription = socket.stream.listen(
      _handleRawMessage,
      onDone: () => _handleDisconnect(socket),
      onError: (Object _, StackTrace _) => _handleDisconnect(socket),
    );
    socket.send(jsonEncode({'type': 'auth', 'token': token}));
  }

  /// Closes the connection permanently — no further reconnect attempts.
  Future<void> disconnect() async {
    _closed = true;
    await _closeSocket();
  }

  /// Closes the connection until [resume] is called — for example while the
  /// user is signed out. Active subscriptions are kept and replayed on resume.
  Future<void> pause() async {
    _paused = true;
    await _closeSocket();
  }

  /// Reopens a [pause]d connection (for example after sign-in).
  void resume() {
    if (!_paused) return;
    _paused = false;
    _backoff = _initialBackoff;
    if (_activeIntents.isNotEmpty) unawaited(connect());
  }

  /// Sends a refreshed access token over the open connection so the server
  /// keeps it authorised past the old token's expiry. If no connection is
  /// open, the next connect uses [getAccessToken] anyway.
  void updateAccessToken() {
    final token = _getAccessToken();
    if (!_ready || token == null || token.isEmpty) return;
    _socket?.send(jsonEncode({'type': 'auth', 'token': token}));
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

  /// Read-state changes for the signed-in user's notifications made on any
  /// device or tab — `notification.read` (one) and `notification.read_all`.
  Stream<Map<String, dynamic>> subscribeToNotificationReads() {
    _addIntent('notifications');
    return _messages.stream.where(
      (m) =>
          m['type'] == 'notification.read' ||
          m['type'] == 'notification.read_all',
    );
  }

  /// Route changes for the signed-in driver — the backend's
  /// `delivery.route_updated` messages on the driver's own channel.
  Stream<Map<String, dynamic>> subscribeToDriverRoutes() {
    _addIntent('driver');
    return _messages.stream.where(
      (m) => m['type'] == 'delivery.route_updated',
    );
  }

  /// The delivery driver's live position for one order — the backend's
  /// `driver.location` messages, published on the same `order:{orderId}`
  /// channel as [subscribeToOrder]'s status events (so this adds no new
  /// subscription intent when a screen already watches the order).
  Stream<Map<String, dynamic>> subscribeToDriverLocation(String orderId) {
    _addIntent('order:$orderId');
    return _messages.stream.where(
      (m) => m['type'] == 'driver.location' && m['order_id'] == orderId,
    );
  }

  void _addIntent(String intent) {
    if (!_activeIntents.add(intent)) return;
    if (_socket == null) {
      unawaited(connect());
    } else if (_ready) {
      _sendSubscribe({intent});
    }
    // Otherwise the intent is sent once the server reports ready.
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

    switch (data['type']) {
      case 'ready':
        _onReady();
      case 'ping':
        _socket?.send(jsonEncode({'type': 'pong'}));
      default:
        _messages.add(data);
    }
  }

  void _onReady() {
    final wasReady = _ready;
    _ready = true;
    // Backoff resets only once the server has accepted the token: a server
    // that accepts the socket and then immediately drops it (mid-outage, or
    // rejecting the token) must keep backing off, not be hammered at 1s.
    _backoff = _initialBackoff;
    if (wasReady) return; // in-band token refresh acknowledgement
    if (_activeIntents.isNotEmpty) _sendSubscribe(_activeIntents);
    if (_everReady) _reconnected.add(null);
    _everReady = true;
  }

  void _handleDisconnect(RealtimeSocket socket) {
    // A replaced socket's late close must not tear down its successor.
    if (!identical(_socket, socket)) return;
    final closeCode = socket.closeCode;
    unawaited(_socketSubscription?.cancel());
    _socketSubscription = null;
    _socket = null;
    _ready = false;
    if (_closed || _paused) return;

    if (closeCode == tokenRejectedCloseCode) {
      final onTokenRejected = _onTokenRejected;
      if (onTokenRejected != null) unawaited(onTokenRejected());
    }
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_closed || _paused) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(_backoff, connect);
    final doubled = _backoff * 2;
    _backoff = doubled > _maxBackoff ? _maxBackoff : doubled;
  }

  Future<void> _closeSocket() async {
    _reconnectTimer?.cancel();
    final socket = _socket;
    final subscription = _socketSubscription;
    _socket = null;
    _socketSubscription = null;
    _ready = false;
    // Close first: the identity guard in [_handleDisconnect] ignores the
    // resulting onDone because [_socket] no longer points at this socket.
    final closing = socket?.close();
    await subscription?.cancel();
    await closing;
  }
}
