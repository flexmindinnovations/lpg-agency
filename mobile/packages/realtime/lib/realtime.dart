/// Live order and notification updates over the backend's single
/// multiplexed `/ws` WebSocket (`backend/src/lpg/api/v1/routers/ws.py`).
library;

export 'src/realtime_client.dart';
export 'src/realtime_socket.dart' show RealtimeSocket, connectRealtimeSocket;
