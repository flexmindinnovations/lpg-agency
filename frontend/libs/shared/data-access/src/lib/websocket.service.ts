import { Injectable, inject, OnDestroy } from '@angular/core';
import { filter, map, Observable, Subject } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

export interface RealtimeMessage {
  type: string;
  [key: string]: any;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private readonly config = inject(ApiConfiguration);
  private socket: WebSocket | null = null;
  private readonly messageSubject = new Subject<RealtimeMessage>();
  private readonly connectionStateSubject = new Subject<'connected' | 'disconnected' | 'connecting'>();
  
  private activeIntents = new Set<string>();
  private reconnectAttempts = 0;
  private reconnectTimeoutId: any = null;
  private isDestroyed = false;

  readonly messages$ = this.messageSubject.asObservable();
  readonly connectionState$ = this.connectionStateSubject.asObservable();

  connect(token: string): void {
    if (this.isDestroyed || this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.connectionStateSubject.next('connecting');
    const wsUrl = this.config.rootUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    const url = `${wsUrl}/api/v1/ws?token=${encodeURIComponent(token)}`;
    
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.connectionStateSubject.next('connected');
      
      // Resubscribe to active intents on reconnect
      if (this.activeIntents.size > 0) {
        this.send({ subscribe: Array.from(this.activeIntents) });
      }
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') {
          this.send({ type: 'pong' });
          return;
        }
        this.messageSubject.next(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    this.socket.onclose = (event) => {
      this.socket = null;
      this.connectionStateSubject.next('disconnected');
      
      // 1008 Policy Violation (invalid token) -> don't auto-reconnect
      // 1000 Normal Closure -> don't auto-reconnect
      if (event.code === 1008 || event.code === 1000) {
        return;
      }
      
      this.scheduleReconnect(token);
    };

    this.socket.onerror = () => {
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
    this.activeIntents.add(intent);
    if (this.socket?.readyState === WebSocket.OPEN) {
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
      this.send({ refresh_token: newToken });
    } else {
      // If disconnected, reconnect with new token
      this.disconnect();
      this.connect(newToken);
    }
  }

  on<T = any>(messageType: string): Observable<T> {
    return this.messages$.pipe(
      filter((msg) => msg.type === messageType),
      map((msg) => msg as T)
    );
  }

  private send(payload: any): void {
    this.socket?.send(JSON.stringify(payload));
  }

  private scheduleReconnect(token: string): void {
    if (this.isDestroyed || this.reconnectTimeoutId) return;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s
    const backoff = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    // Add up to 20% jitter
    const jitter = backoff * 0.2 * Math.random();
    const delay = backoff + jitter;

    this.reconnectAttempts++;
    
    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectTimeoutId = null;
      this.connect(token);
    }, delay);
  }

  ngOnDestroy(): void {
    this.isDestroyed = true;
    this.disconnect();
    this.messageSubject.complete();
    this.connectionStateSubject.complete();
  }
}
