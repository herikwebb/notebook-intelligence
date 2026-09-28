// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

// Converting is a local copy. It must not reach a model: summaries are made
// only when a converted code cell later runs.
const summarizeChatbookCell = jest.fn();

jest.mock('@jupyterlab/cells', () => ({ CodeCell: class {} }), {
  virtual: true
});
jest.mock('@jupyterlab/codemirror', () => ({}), { virtual: true });
jest.mock('@codemirror/view', () => ({}), { virtual: true });
jest.mock('@jupyterlab/notebook', () => ({ NotebookPanel: class {} }), {
  virtual: true
});
jest.mock('@jupyterlab/services', () => ({}), { virtual: true });
jest.mock('../../src/api', () => ({
  NBIAPI: {
    config: {},
    configChanged: { connect: () => undefined },
    summarizeChatbookCell: (...args: unknown[]) =>
      summarizeChatbookCell(...args)
  }
}));
jest.mock('../../src/chatbook-mentions', () => ({
  setChatbookMentionsEnabled: () => undefined
}));
jest.mock('../../src/utils', () => ({ cellOutputAsText: () => '' }));
jest.mock('../../src/notebook-kernels', () => ({
  sharedKernelSpecManager: () => ({
    ready: Promise.resolve(),
    specs: { kernelspecs: {} }
  }),
  resolveChatbookBackendProfile: () => ({
    language: 'python',
    displayName: 'Python'
  }),
  mimeTypeForNotebookLanguage: () => 'text/x-python'
}));

import { convertNotebookToChatbook } from '../../src/chatbook';

// jsdom lacks structuredClone, which the browser and Node both provide.
(globalThis as any).structuredClone ??= (value: unknown) =>
  JSON.parse(JSON.stringify(value));

describe('convertNotebookToChatbook', () => {
  const notebook = {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: {
        name: 'python3',
        display_name: 'Python 3',
        language: 'python'
      }
    },
    cells: [
      {
        id: 'c1',
        cell_type: 'code',
        source: 'x = 1',
        metadata: {},
        outputs: [],
        execution_count: null
      }
    ]
  };

  it('writes a Chatbook copy next to the notebook without asking a model anything', async () => {
    const fetchSpy = jest.fn();
    (globalThis as any).fetch = fetchSpy;
    const saved: { path: string; content: any }[] = [];
    const existing = new Set(['work/analysis-chatbook.ipynb']);
    const contents = {
      get: jest.fn(async (path: string) => {
        if (existing.has(path)) {
          return { path };
        }
        throw new Error('not found');
      }),
      save: jest.fn(async (path: string, model: any) => {
        saved.push({ path, content: model.content });
        return { path };
      })
    } as any;
    const panel = {
      model: { toJSON: () => notebook },
      context: { path: 'work/analysis.ipynb' }
    } as any;

    const path = await convertNotebookToChatbook(panel, contents);

    // The first name is taken, so the copy is numbered rather than overwritten.
    expect(path).toBe('work/analysis-chatbook-1.ipynb');
    expect(saved.map(item => item.path)).toEqual([
      'work/analysis-chatbook-1.ipynb'
    ]);
    expect(saved[0].content.metadata.kernelspec.name).toBe('chatbook');
    expect(saved[0].content.cells[0].metadata.nbi.chatbook.mode).toBe('code');
    // The notebook it was made from is untouched.
    expect((notebook.cells[0].metadata as any).nbi).toBeUndefined();
    expect(summarizeChatbookCell).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
