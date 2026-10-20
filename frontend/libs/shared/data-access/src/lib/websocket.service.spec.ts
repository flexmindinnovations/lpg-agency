import { TestBed } from '@angular/core/testing';
import { ApiConfiguration } from './generated/api-configuration';
import { AuthTokenStore } from './auth-token.store';
import { WebSocketService } from './websocket.service';

/** Minimal stand-in for the browser `WebSocket`, driven by the test. */
class FakeSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: FakeSocket[] = [];

  readyState = FakeSocket.CONNECTING;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data));
  }

  close(code = 1000): void {
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.({ code });
  }

  open(): void {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  receive(message: object): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  drop(code = 1006): void {
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.({ code });
  }
}

describe('WebSocketService', () => {
  let service: WebSocketService;
  const realWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    jest.useFakeTimers();
    FakeSocket.instances = [];
    (globalThis as any).WebSocket = FakeSocket;
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiConfiguration, useValue: { rootUrl: 'https://lpg.example' } },
        { provide: AuthTokenStore, useValue: { accessToken: () => 'fresh-token' } },
      ],
    });
    service = TestBed.inject(WebSocketService);
  });

  afterEach(() => {
    service.ngOnDestroy();
    (globalThis as any).WebSocket = realWebSocket;
    jest.useRealTimers();
  });

  it('never puts the token in the URL; it is the first frame', () => {
    service.connect('secret-token');
    const socket = FakeSocket.instances[0];
    expect(socket.url).toBe('wss://lpg.example/api/v1/ws');
    expect(socket.url).not.toContain('secret-token');

    socket.open();
    expect(socket.sent[0]).toEqual({ type: 'auth', token: 'secret-token' });
  });

  it('subscribes only once the server says ready, then on each later intent', () => {
    service.subscribeTo('notifications');
    service.connect('t');
    const socket = FakeSocket.instances[0];
    socket.open();
    expect(socket.sent).toHaveLength(1); // just the auth frame

    socket.receive({ type: 'ready' });
    expect(socket.sent[1]).toEqual({ subscribe: ['notifications'] });

    service.subscribeTo('orders');
    service.subscribeTo('orders');
    expect(socket.sent.slice(2)).toEqual([{ subscribe: ['orders'] }]);
  });

  it('reconnects with backoff, resubscribes with the current token and announces it', () => {
    const reconnected = jest.fn();
    service.reconnected$.subscribe(reconnected);
    service.subscribeTo('notifications');
    service.connect('old-token');
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].receive({ type: 'ready' });
    expect(reconnected).not.toHaveBeenCalled();

    FakeSocket.instances[0].drop();
    jest.advanceTimersByTime(1300);
    const second = FakeSocket.instances[1];
    expect(second).toBeDefined();
    second.open();
    expect(second.sent[0]).toEqual({ type: 'auth', token: 'fresh-token' });
    second.receive({ type: 'ready' });
    expect(second.sent[1]).toEqual({ subscribe: ['notifications'] });
    expect(reconnected).toHaveBeenCalledTimes(1);
  });

  it('asks for a fresh token on 1008 instead of retrying', () => {
    const rejected = jest.fn();
    service.tokenRejected$.subscribe(rejected);
    service.connect('expired');
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].drop(1008);
    jest.advanceTimersByTime(60000);
    expect(rejected).toHaveBeenCalledTimes(1);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('changes$ fires on the listed message types and on reconnect', () => {
    const changed = jest.fn();
    service.changes$('order.status_changed').subscribe(changed);
    service.connect('t');
    const socket = FakeSocket.instances[0];
    socket.open();
    socket.receive({ type: 'ready' });
    socket.receive({ type: 'notification.new' });
    socket.receive({ type: 'order.status_changed', order_id: 'o1' });
    expect(changed).toHaveBeenCalledTimes(1);

    socket.drop();
    jest.advanceTimersByTime(1300);
    FakeSocket.instances[1].open();
    FakeSocket.instances[1].receive({ type: 'ready' });
    expect(changed).toHaveBeenCalledTimes(2);
  });

  it('a replaced socket closing late does not tear down its successor', () => {
    service.connect('a');
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].receive({ type: 'ready' });
    service.refreshToken('b'); // open: refreshed in-band, same socket
    expect(FakeSocket.instances[0].sent.at(-1)).toEqual({ type: 'auth', token: 'b' });
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
