// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { Notification } from '@jupyterlab/apputils';

import { attachTerminalDragDrop } from '../../src/terminal-drag';
import {
  formatForMode,
  invertMode,
  isTerminalSafePath,
  partitionTerminalSafePaths
} from '../../src/terminal-drag-format';

describe('formatForMode', () => {
  it('prefixes each path with @ in mention mode', () => {
    expect(formatForMode(['/tmp/a.txt', '/tmp/b.txt'], 'mention')).toBe(
      '@/tmp/a.txt @/tmp/b.txt'
    );
  });

  it('shell-escapes each path in raw mode', () => {
    expect(formatForMode(['/tmp/a.txt', '/tmp/with space.txt'], 'raw')).toBe(
      "'/tmp/a.txt' '/tmp/with space.txt'"
    );
  });

  it('returns empty string for empty input in either mode', () => {
    expect(formatForMode([], 'mention')).toBe('');
    expect(formatForMode([], 'raw')).toBe('');
  });

  it('handles a single path in mention mode', () => {
    expect(formatForMode(['/tmp/only.txt'], 'mention')).toBe('@/tmp/only.txt');
  });

  it('does not quote the @-prefix in mention mode', () => {
    // Intentional: Claude Code parses bare @<path> tokens, so wrapping them
    // in shell quotes would break the parse. Mention mode trusts the path
    // not to contain shell metacharacters; raw mode is the path that quotes.
    expect(formatForMode(['/tmp/a b.txt'], 'mention')).toBe('@/tmp/a b.txt');
  });
});

describe('isTerminalSafePath', () => {
  it('accepts ordinary paths, including spaces, quotes and non-ASCII', () => {
    expect(isTerminalSafePath('/tmp/a b.txt')).toBe(true);
    expect(isTerminalSafePath("/tmp/it's.txt")).toBe(true);
    expect(isTerminalSafePath('/tmp/données/ファイル.csv')).toBe(true);
  });

  it('rejects paths carrying line breaks, which xterm pastes as Enter', () => {
    expect(isTerminalSafePath('/tmp/a\nrm -rf ~\nb.txt')).toBe(false);
    expect(isTerminalSafePath('/tmp/a\r\nb.txt')).toBe(false);
    expect(isTerminalSafePath('/tmp/a\rb.txt')).toBe(false);
  });

  it('rejects other C0 / DEL / C1 control characters', () => {
    expect(isTerminalSafePath('/tmp/a\u001b]0;x\u0007b.txt')).toBe(false);
    expect(isTerminalSafePath('/tmp/a\tb.txt')).toBe(false);
    expect(isTerminalSafePath('/tmp/a\u007fb.txt')).toBe(false);
    expect(isTerminalSafePath('/tmp/a\u0085b.txt')).toBe(false);
  });
});

describe('partitionTerminalSafePaths', () => {
  it('keeps order and separates unsafe paths from safe ones', () => {
    expect(
      partitionTerminalSafePaths(['/tmp/a.txt', '/tmp/x\ny', '/tmp/b.txt'])
    ).toEqual({
      safe: ['/tmp/a.txt', '/tmp/b.txt'],
      rejected: ['/tmp/x\ny']
    });
  });
});

describe('invertMode', () => {
  it('returns the original mode when shouldInvert is false', () => {
    expect(invertMode('mention', false)).toBe('mention');
    expect(invertMode('raw', false)).toBe('raw');
  });

  it('flips mention to raw and back when shouldInvert is true', () => {
    expect(invertMode('mention', true)).toBe('raw');
    expect(invertMode('raw', true)).toBe('mention');
  });
});

describe('attachTerminalDragDrop lm-drop handler', () => {
  type ConnectSlot = (sender: unknown, widget: unknown) => void;
  type DisposedSlot = () => void;

  interface ITestWidgetEnv {
    mock: any;
    host: HTMLElement;
    paste: jest.Mock;
    activate: jest.Mock;
    fireDisposed: () => void;
  }

  function setupTracker(): {
    tracker: any;
    fireWidgetAdded: (widget: unknown) => void;
  } {
    let widgetAddedSlot: ConnectSlot | null = null;
    const tracker = {
      widgetAdded: {
        connect: (slot: ConnectSlot) => {
          widgetAddedSlot = slot;
        }
      },
      forEach: (_fn: (widget: unknown) => void) => undefined
    };
    return {
      tracker,
      fireWidgetAdded: (widget: unknown) => {
        if (!widgetAddedSlot) {
          throw new Error('widgetAdded was never wired');
        }
        widgetAddedSlot(null, widget);
      }
    };
  }

  function buildWidget(): ITestWidgetEnv {
    const host = document.createElement('div');
    document.body.appendChild(host);
    const paste = jest.fn();
    const activate = jest.fn();
    let isDisposed = false;
    const disposedSlots: DisposedSlot[] = [];
    const mock = {
      node: host,
      content: { paste },
      toolbar: { addItem: jest.fn().mockReturnValue(true) },
      disposed: {
        connect: (slot: DisposedSlot) => {
          disposedSlots.push(slot);
        }
      },
      activate,
      get isDisposed() {
        return isDisposed;
      }
    };
    return {
      mock,
      host,
      paste,
      activate,
      fireDisposed: () => {
        isDisposed = true;
        disposedSlots.forEach(slot => slot());
      }
    };
  }

  function dispatchLmDrop(target: EventTarget, paths: string[]): void {
    const event: any = new Event('lm-drop', {
      bubbles: true,
      cancelable: true
    });
    event.mimeData = {
      hasData: (key: string) => key === 'application/x-jupyter-icontents',
      getData: (key: string) =>
        key === 'application/x-jupyter-icontents' ? paths : null
    };
    event.proposedAction = 'move';
    event.dropAction = 'none';
    event.shiftKey = false;
    target.dispatchEvent(event);
  }

  // Each test must dispose its widget so the document-level lm-* listeners
  // attached by setupTerminal don't leak across tests in this file.
  const envs: ITestWidgetEnv[] = [];
  afterEach(() => {
    envs.splice(0).forEach(env => {
      env.fireDisposed();
      if (env.host.parentNode) {
        env.host.parentNode.removeChild(env.host);
      }
    });
  });

  function newEnv(): ITestWidgetEnv {
    const env = buildWidget();
    envs.push(env);
    return env;
  }

  it('activates the widget after pasting so the next Enter goes to xterm, not the file-browser', () => {
    const env = newEnv();
    const { tracker, fireWidgetAdded } = setupTracker();
    attachTerminalDragDrop({ tracker, isEnabled: () => true });
    fireWidgetAdded(env.mock);

    dispatchLmDrop(env.host, ['/tmp/file.txt']);

    expect(env.paste).toHaveBeenCalledTimes(1);
    expect(env.paste).toHaveBeenCalledWith('@/tmp/file.txt ');
    expect(env.activate).toHaveBeenCalledTimes(1);
    // Activate must run after paste so the terminal owns focus before the
    // user presses Enter; otherwise the file-browser's "open selected item"
    // handler eats the first keypress.
    expect(env.activate.mock.invocationCallOrder[0]).toBeGreaterThan(
      env.paste.mock.invocationCallOrder[0]
    );
  });

  it('refuses to paste a path with an embedded line break and warns instead', () => {
    const env = newEnv();
    const { tracker, fireWidgetAdded } = setupTracker();
    attachTerminalDragDrop({ tracker, isEnabled: () => true });
    fireWidgetAdded(env.mock);
    (Notification.warning as jest.Mock).mockClear();

    // A file named "report\nrm -rf ~\n.csv" is legal on POSIX and listed
    // verbatim by the contents API; pasted unquoted it would run the
    // middle line as a command.
    dispatchLmDrop(env.host, ['/tmp/report\nrm -rf ~\n.csv']);

    expect(env.paste).not.toHaveBeenCalled();
    expect(env.activate).not.toHaveBeenCalled();
    expect(Notification.warning).toHaveBeenCalledTimes(1);
    expect((Notification.warning as jest.Mock).mock.calls[0][0]).toMatch(
      /skipped 1 path containing control characters/
    );
  });

  it('still pastes the safe paths of a mixed drop, in both modes', () => {
    const env = newEnv();
    const { tracker, fireWidgetAdded } = setupTracker();
    attachTerminalDragDrop({ tracker, isEnabled: () => true });
    fireWidgetAdded(env.mock);
    (Notification.warning as jest.Mock).mockClear();

    dispatchLmDrop(env.host, [
      '/tmp/ok.txt',
      '/tmp/bad\u001b[2Jname',
      '/tmp/also\rbad'
    ]);

    expect(env.paste).toHaveBeenCalledTimes(1);
    expect(env.paste).toHaveBeenCalledWith('@/tmp/ok.txt ');
    expect(env.activate).toHaveBeenCalledTimes(1);
    expect((Notification.warning as jest.Mock).mock.calls[0][0]).toMatch(
      /skipped 2 paths containing control characters/
    );

    // Raw mode single-quotes for POSIX shells, but the terminal may be
    // running a REPL, so the guard applies before quoting in both modes.
    const rawEvent: any = new Event('lm-drop', {
      bubbles: true,
      cancelable: true
    });
    rawEvent.mimeData = {
      hasData: (key: string) => key === 'application/x-jupyter-icontents',
      getData: (key: string) =>
        key === 'application/x-jupyter-icontents'
          ? ['/tmp/raw ok.txt', '/tmp/raw\nbad']
          : null
    };
    rawEvent.proposedAction = 'move';
    rawEvent.dropAction = 'none';
    rawEvent.shiftKey = true;
    env.host.dispatchEvent(rawEvent);

    expect(env.paste).toHaveBeenCalledTimes(2);
    expect(env.paste).toHaveBeenLastCalledWith("'/tmp/raw ok.txt' ");
  });

  it('handles drops on a descendant of the terminal host, not just the host itself', () => {
    const env = newEnv();
    const inner = document.createElement('div');
    env.host.appendChild(inner);
    const { tracker, fireWidgetAdded } = setupTracker();
    attachTerminalDragDrop({ tracker, isEnabled: () => true });
    fireWidgetAdded(env.mock);

    dispatchLmDrop(inner, ['/tmp/nested.txt']);

    expect(env.paste).toHaveBeenCalledWith('@/tmp/nested.txt ');
    expect(env.activate).toHaveBeenCalled();
  });
});
