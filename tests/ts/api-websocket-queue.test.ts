// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { Notification } from '@jupyterlab/apputils';
import { ServerConnection } from '@jupyterlab/services';
import { NBIAPI } from '../../src/api';
import { BackendMessageType, RequestDataType } from '../../src/tokens';

class FakeSocket {
  static created: FakeSocket[] = [];
  readyState: number = WebSocket.CONNECTING;
  sent: any[] = [];
  onopen: (() => void) | null = null;
  onclose: ((e: { reason: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.created.push(this);
  }
  send(text: string) {
    this.sent.push(JSON.parse(text));
  }
  close() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.({ reason: 'closed' });
  }
  open() {
    this.readyState = WebSocket.OPEN;
    this.onopen?.();
  }
}

const sentIds = (socket: FakeSocket) =>
  socket.sent.map(m => `${m.type}:${m.id}`);

// What reaches the frontend's listeners (StreamEnd for unsent requests).
let received: any[] = [];
const listen = (_: unknown, msg: string) => received.push(JSON.parse(msg));
const warning = jest.fn();

beforeEach(() => {
  jest.useFakeTimers();
  FakeSocket.created = [];
  received = [];
  warning.mockClear();
  jest.spyOn(Notification, 'warning').mockImplementation(warning);
  jest.spyOn(ServerConnection, 'makeSettings').mockReturnValue({
    wsUrl: 'ws://localhost/',
    WebSocket: FakeSocket
  } as any);
  NBIAPI._pendingMessages = [];
  (NBIAPI as any)._webSocket = undefined;
  void NBIAPI.initializeWebsocket();
  (NBIAPI as any)._messageReceived.connect(listen);
});

afterEach(() => {
  (NBIAPI as any)._messageReceived.disconnect(listen);
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('chat WebSocket sends', () => {
  it('holds messages while connecting and sends them in order on open', () => {
    const socket = FakeSocket.created[0];
    NBIAPI.sendWebSocketMessage('a', RequestDataType.ChatUserInput, {});
    NBIAPI.sendWebSocketMessage('b', RequestDataType.ClearChatHistory, {});
    expect(socket.sent).toEqual([]);

    socket.open();
    expect(sentIds(socket)).toEqual([
      `${RequestDataType.ChatUserInput}:a`,
      `${RequestDataType.ClearChatHistory}:b`
    ]);
    NBIAPI.sendWebSocketMessage('c', RequestDataType.ChatUserInput, {});
    expect(socket.sent).toHaveLength(3);
  });

  it('sends a queued request and its cancellation, so the server ends it', () => {
    const socket = FakeSocket.created[0];
    NBIAPI.sendWebSocketMessage('turn', RequestDataType.ChatRequest, {});
    NBIAPI.sendWebSocketMessage('turn', RequestDataType.CancelChatRequest, {});
    socket.open();
    expect(sentIds(socket)).toEqual([
      `${RequestDataType.ChatRequest}:turn`,
      `${RequestDataType.CancelChatRequest}:turn`
    ]);
  });

  it('ends the requests a connecting socket never sent when it closes', () => {
    const first = FakeSocket.created[0];
    NBIAPI.sendWebSocketMessage('chat', RequestDataType.ChatRequest, {});
    NBIAPI.sendWebSocketMessage('reply', RequestDataType.ChatUserInput, {});
    first.close();
    // The request's caller is released, and told why; the reply is not a
    // request and just goes.
    expect(received).toEqual([
      { id: 'chat', type: BackendMessageType.StreamEnd, data: {} }
    ]);
    expect(warning).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(1000);
    const second = FakeSocket.created[1];
    second.open();
    // A new connection has none of the old one's server-side state.
    expect(second.sent).toEqual([]);
  });

  it('ends a request sent with no open socket instead of leaving it waiting', () => {
    const socket = FakeSocket.created[0];
    socket.open();
    socket.readyState = WebSocket.CLOSED;
    NBIAPI.sendWebSocketMessage(
      'inline',
      RequestDataType.InlineCompletionRequest,
      {}
    );
    expect(received).toEqual([
      { id: 'inline', type: BackendMessageType.StreamEnd, data: {} }
    ]);
    // A background inline completion is not worth a notice.
    expect(warning).not.toHaveBeenCalled();
  });

  it('closes a socket it replaces and ignores what that socket still says', () => {
    const stale = FakeSocket.created[0];
    stale.open();
    void NBIAPI.initializeWebsocket();
    const current = FakeSocket.created[1];
    expect(stale.readyState).toBe(WebSocket.CLOSED);
    // Its close did not schedule another connection.
    jest.advanceTimersByTime(1000);
    expect(FakeSocket.created).toHaveLength(2);

    stale.onmessage?.({ data: JSON.stringify({ id: 'x', type: 'late' }) });
    expect(received).toEqual([]);

    NBIAPI.sendWebSocketMessage('a', RequestDataType.ChatUserInput, {});
    current.open();
    expect(sentIds(current)).toEqual([`${RequestDataType.ChatUserInput}:a`]);
  });
});
