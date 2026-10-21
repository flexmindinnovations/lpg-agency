import { Injectable, inject, OnDestroy } from '@angular/core';
import { filter, map, merge, Observable, Subject } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { AuthTokenStore } from './auth-token.store';

export interface RealtimeMessage {
  type: string;
  [key: string]: any;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private readonly config = inject(ApiConfiguration);
  private readonly tokenStore = inject(AuthTokenStore);
  private socket: WebSocket | null = null;
  private readonly messageSubject = new Subject<RealtimeMessage>();
  private readonly connectionStateSubject = new Subject<
    'connected' | 'disconnected' | 'connecting'
  >();
  private readonly tokenRejectedSubject = new Subject<void>();
  private readonly reconnectedSubject = new Subject<void>();
  /** The server has accepted this socket's auth frame at least once. */
  private hasBeenReady = false;

  private activeIntents = new Set<string>();
  private reconnectAttempts = 0;
  private reconnectTimeoutId: any = null;
  private isDestroyed = false;

  readonly messages$ = this.messageSubject.asObservable();
  readonly connectionState$ = this.connectionStateSubject.asObservable();
  /**
   * The server closed the socket with 1008: the access token it was opened
   * with has expired (they last 15 minutes). `AuthService` answers with a
   * refresh, whose `refreshToken()` call reopens the socket. Without this
   * an idle tab whose socket dropped stayed offline until the next HTTP 401.
   */
  readonly tokenRejected$ = this.tokenRejectedSubject.asObservable();
  /**
   * The socket is back after a drop. Messages published while it was down
   * are gone (Redis Pub/Sub keeps nothing), so screens refetch what they
   * show — see `changes$`.
   */
  readonly reconnected$ = this.reconnectedSubject.asObservable();

  connect(token: string): void {
    if (
      this.isDestroyed ||
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.connectionStateSubject.next('connecting');
    const wsUrl = this.config.rootUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    // No credentials in the URL — it would land in access logs (DO-38). The
    // token goes in the first frame, inside the TLS stream.
    const socket = new WebSocket(`${wsUrl}/api/v1/ws`);
    this.socket = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'auth', token }));
    };

    socket.onmessage = (event) => {
      if (this.socket !== socket) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') {
          this.send({ type: 'pong' });
          return;
        }
        if (data.type === 'ready') {
          this.onReady();
          return;
        }
        this.messageSubject.next(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    socket.onclose = (event) => {
      // A socket replaced by `refreshToken()`/`disconnect()` closing late
      // must not tear down its successor.
      if (this.socket !== socket) return;
      this.socket = null;
      this.connectionStateSubject.next('disconnected');

      // 1000 Normal Closure -> don't auto-reconnect
      if (event.code === 1000) {
        return;
      }
      // 1008 Policy Violation (invalid token) -> retrying with the same token
      // is pointless; ask for a fresh one instead.
      if (event.code === 1008) {
        this.tokenRejectedSubject.next();
        return;
      }

      this.scheduleReconnect();
    };

    socket.onerror = () => {
      // Browser handles the actual error logging. onclose will fire next.
    };
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.close(1000);
      this.socket = null;
    }
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    this.connectionStateSubject.next('disconnected');
  }

  subscribeTo(intent: string): void {
    if (this.activeIntents.has(intent)) return;
    this.activeIntents.add(intent);
    if (this.socket?.readyState === WebSocket.OPEN && this.hasBeenReady) {
      this.send({ subscribe: [intent] });
    }
  }

  unsubscribeFrom(intent: string): void {
    this.activeIntents.delete(intent);
    // Realtime design in this platform allows subscriptions to just drop when socket reconnects,
    // or we could send an 'unsubscribe' payload if the backend supported it. For now, it's just removed
    // from the active intents set so it doesn't get re-sent on reconnect.
  }

  refreshToken(newToken: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.send({ type: 'auth', token: newToken });
    } else {
      // If disconnected, reconnect with new token
      this.disconnect();
      this.connect(newToken);
    }
  }

  on<T = any>(messageType: string): Observable<T> {
    return this.messages$.pipe(
      filter((msg) => msg.type === messageType),
      map((msg) => msg as T),
    );
  }

  /**
   * Fires for any of `messageTypes`, and after every reconnect — the one
   * stream a live screen needs to stay current: reload on it (debounced).
   */
  changes$(...messageTypes: string[]): Observable<void> {
    return merge(
      this.messages$.pipe(filter((msg) => messageTypes.includes(msg.type))),
      this.reconnected$,
    ).pipe(map(() => undefined));
  }

  /** Authenticated: (re)subscribe, and tell screens if this is a reconnect. */
  private onReady(): void {
    this.reconnectAttempts = 0;
    this.connectionStateSubject.next('connected');
    // The server forgets a dropped socket's subscriptions.
    if (this.activeIntents.size > 0) {
      this.send({ subscribe: Array.from(this.activeIntents) });
    }
    if (this.hasBeenReady) {
      this.reconnectedSubject.next();
    }
    this.hasBeenReady = true;
  }

  private send(payload: any): void {
    this.socket?.send(JSON.stringify(payload));
  }

  private scheduleReconnect(): void {
    if (this.isDestroyed || this.reconnectTimeoutId) return;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s
    const backoff = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    // Add up to 20% jitter
    const jitter = backoff * 0.2 * Math.random();
    const delay = backoff + jitter;

    this.reconnectAttempts++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectTimeoutId = null;
      // The token the socket first opened with may have been refreshed (or
      // expired) since; reconnect with whatever is current.
      const token = this.tokenStore.accessToken();
      if (token) this.connect(token);
    }, delay);
  }

  ngOnDestroy(): void {
    this.isDestroyed = true;
    this.disconnect();
    this.messageSubject.complete();
    this.connectionStateSubject.complete();
    this.tokenRejectedSubject.complete();
    this.reconnectedSubject.complete();
  }
}
