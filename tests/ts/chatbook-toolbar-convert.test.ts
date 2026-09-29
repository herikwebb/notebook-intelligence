// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

const showDialog = jest.fn();
const convertNotebookToChatbook = jest.fn();
const config: Record<string, unknown> = {};
let backend = { kernelName: 'python3', language: 'python', displayName: '' };
let installedProfiles: { language: string }[] = [];

jest.mock('@jupyterlab/apputils', () => ({
  Dialog: {
    cancelButton: (options: Record<string, unknown> = {}) => ({
      label: 'Cancel',
      ...options,
      accept: false
    }),
    okButton: (options: Record<string, unknown> = {}) => ({
      label: 'OK',
      ...options,
      accept: true
    })
  },
  showDialog: (...args: unknown[]) => showDialog(...args)
}));
jest.mock(
  '@jupyterlab/ui-components',
  () => ({ LabIcon: class {}, ToolbarButton: class {} }),
  { virtual: true }
);
jest.mock('@jupyterlab/notebook', () => ({}), { virtual: true });
jest.mock('@jupyterlab/application', () => ({}), { virtual: true });
jest.mock('@jupyterlab/docregistry', () => ({}), { virtual: true });
jest.mock('@lumino/disposable', () => ({ DisposableDelegate: class {} }), {
  virtual: true
});
jest.mock('../../src/api', () => ({ NBIAPI: { config } }));
jest.mock('../../src/chatbook', () => ({
  convertNotebookToChatbook: (...args: unknown[]) =>
    convertNotebookToChatbook(...args),
  exportChatbookNotebookAsCode: jest.fn(),
  isChatbookSession: (session: { kernelName?: string }) =>
    session.kernelName === 'chatbook',
  nextChatbookNotebookMode: jest.fn(),
  toggleAllChatbookCellModes: jest.fn()
}));
jest.mock('../../src/notebook-kernels', () => ({
  NotebookKernelNotFoundError: class extends Error {},
  findKernelProfile: jest.fn(),
  listChatbookBackendProfiles: () => installedProfiles,
  resolveChatbookBackendProfile: () => backend,
  sharedKernelSpecManager: () => ({
    ready: Promise.resolve(),
    specs: { kernelspecs: {} }
  })
}));

import {
  canConvertToChatbook,
  confirmConvertToChatbook
} from '../../src/chatbook-toolbar';
import { CommandIDs } from '../../src/command-ids';

function makePanel(
  metadata: Record<string, unknown>,
  options: { kernelName?: string; isReady?: boolean; noModel?: boolean } = {}
): any {
  return {
    model: options.noModel
      ? null
      : { metadata, getMetadata: (key: string) => metadata[key] },
    context: { isReady: options.isReady ?? true, path: 'analysis.ipynb' },
    sessionContext: { kernelName: options.kernelName ?? 'python3' }
  };
}

const python = {
  kernelspec: { name: 'python3', display_name: 'Python 3', language: 'python' }
};
const r = {
  kernelspec: { name: 'ir', display_name: 'R 4.3', language: 'R' }
};

function makeApp(): any {
  return {
    commands: { execute: jest.fn(async () => undefined) },
    serviceManager: { contents: {} }
  };
}

beforeEach(() => {
  config.chatbookEnabled = true;
  backend = {
    kernelName: 'python3',
    language: 'python',
    displayName: 'Python 3 (ipykernel)'
  };
  installedProfiles = [{ language: 'python' }];
  convertNotebookToChatbook.mockResolvedValue('analysis-chatbook.ipynb');
});

describe('canConvertToChatbook', () => {
  it('offers conversion on an ordinary loaded notebook', () => {
    expect(canConvertToChatbook(makePanel(python))).toBe(true);
  });

  it('does not offer it for a Chatbook, running or opened with No Kernel', () => {
    expect(
      canConvertToChatbook(makePanel(python, { kernelName: 'chatbook' }))
    ).toBe(false);
    const chatbook = { kernelspec: { name: 'chatbook', language: 'chatbook' } };
    expect(canConvertToChatbook(makePanel(chatbook, { kernelName: '' }))).toBe(
      false
    );
  });

  it('waits for the file to load, and respects the Chatbook policy', () => {
    expect(canConvertToChatbook(makePanel(python, { isReady: false }))).toBe(
      false
    );
    expect(canConvertToChatbook(makePanel(python, { noModel: true }))).toBe(
      false
    );
    config.chatbookEnabled = false;
    expect(canConvertToChatbook(makePanel(python))).toBe(false);
  });
});

describe('confirmConvertToChatbook', () => {
  it('converts, opens the copy, and reports where it went', async () => {
    showDialog.mockResolvedValue({ button: { accept: true } });
    const app = makeApp();
    await confirmConvertToChatbook(app, makePanel(python));

    expect(showDialog.mock.calls[0][0].title).toBe('Convert to Chatbook');
    expect(convertNotebookToChatbook).toHaveBeenCalledTimes(1);
    expect(app.commands.execute).toHaveBeenCalledWith('docmanager:open', {
      path: 'analysis-chatbook.ipynb'
    });
    expect(app.commands.execute).toHaveBeenCalledWith(
      'apputils:notify',
      expect.objectContaining({
        message: 'Created Chatbook copy: analysis-chatbook.ipynb',
        type: 'success'
      })
    );
  });

  it('does nothing when the user cancels', async () => {
    showDialog.mockResolvedValue({ button: { accept: false } });
    const app = makeApp();
    await confirmConvertToChatbook(app, makePanel(python));
    expect(convertNotebookToChatbook).not.toHaveBeenCalled();
    expect(app.commands.execute).not.toHaveBeenCalled();
  });

  it('treats a py notebook as Python', async () => {
    showDialog.mockResolvedValue({ button: { accept: false } });
    const py = { kernelspec: { name: 'conda-env', language: 'py' } };
    await confirmConvertToChatbook(makeApp(), makePanel(py));
    expect(showDialog.mock.calls[0][0].title).toBe('Convert to Chatbook');
    expect(showDialog.mock.calls[0][0].body).toContain('instead of conda-env');
  });

  it('converts a notebook that records no language, naming the kernel it will use', async () => {
    showDialog.mockResolvedValue({ button: { accept: true } });
    await confirmConvertToChatbook(makeApp(), makePanel({}));
    const dialog = showDialog.mock.calls[0][0];
    expect(dialog.title).toBe('Convert to Chatbook');
    expect(dialog.body).toContain(
      'Its code will run in Python 3 (ipykernel), the Chatbook execution kernel.'
    );
    expect(convertNotebookToChatbook).toHaveBeenCalledTimes(1);
  });

  it('blocks another language and offers the settings when a kernel for it is installed', async () => {
    installedProfiles = [{ language: 'python' }, { language: 'r' }];
    showDialog.mockResolvedValue({ button: { accept: true } });
    const app = makeApp();
    await confirmConvertToChatbook(app, makePanel(r));

    const dialog = showDialog.mock.calls[0][0];
    expect(dialog.title).toBe("Can't convert this notebook yet");
    expect(dialog.body).toContain('written in R,');
    expect(dialog.body).toContain('Execution kernel to a kernel for R,');
    expect(dialog.buttons.map((b: { label: string }) => b.label)).toEqual([
      'Cancel',
      'Open Chatbook settings'
    ]);
    expect(convertNotebookToChatbook).not.toHaveBeenCalled();
    expect(app.commands.execute).toHaveBeenCalledWith(
      CommandIDs.openConfigurationDialog,
      { tab: 'chatbook' }
    );
  });

  it('blocks another language with only Close when no kernel for it is installed', async () => {
    showDialog.mockResolvedValue({ button: { accept: false } });
    const app = makeApp();
    await confirmConvertToChatbook(app, makePanel(r));

    const dialog = showDialog.mock.calls[0][0];
    expect(dialog.body).toContain('No R kernel is installed');
    expect(dialog.buttons).toEqual([
      expect.objectContaining({ label: 'Close', accept: false })
    ]);
    expect(convertNotebookToChatbook).not.toHaveBeenCalled();
    expect(app.commands.execute).not.toHaveBeenCalled();
  });

  it('runs one conversion at a time', async () => {
    let answer: (value: unknown) => void = () => undefined;
    showDialog.mockReturnValue(
      new Promise(resolve => {
        answer = resolve;
      })
    );
    const app = makeApp();
    const panel = makePanel(python);
    const first = confirmConvertToChatbook(app, panel);
    const second = confirmConvertToChatbook(app, panel);
    await second;
    answer({ button: { accept: true } });
    await first;
    expect(showDialog).toHaveBeenCalledTimes(1);
    expect(convertNotebookToChatbook).toHaveBeenCalledTimes(1);
  });

  it('reports a failed save and opens nothing', async () => {
    showDialog.mockResolvedValue({ button: { accept: true } });
    convertNotebookToChatbook.mockRejectedValue(new Error('read-only'));
    const app = makeApp();
    await confirmConvertToChatbook(app, makePanel(python));
    expect(app.commands.execute).toHaveBeenCalledTimes(1);
    expect(app.commands.execute).toHaveBeenCalledWith(
      'apputils:notify',
      expect.objectContaining({
        message: 'Could not convert to Chatbook: read-only',
        type: 'error'
      })
    );
  });
});
