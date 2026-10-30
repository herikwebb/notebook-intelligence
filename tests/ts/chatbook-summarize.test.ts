// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

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
  mimeTypeForNotebookLanguage: () => 'text/x-python'
}));

import { summarizeCodeCell } from '../../src/chatbook';
import { chatbookSummaryHash } from '../../src/chatbook-core';

function makeCell(source: string, chatbook: Record<string, unknown>) {
  const model: any = {
    metadata: { nbi: { chatbook } },
    setMetadata(key: string, value: unknown) {
      this.metadata = { ...this.metadata, [key]: value };
    },
    sharedModel: {
      getSource: () => source,
      setSource: (value: string) => {
        source = value;
      }
    }
  };
  return {
    model,
    edit: (value: string) => {
      source = value;
    }
  };
}

const meta = (cell: { model: any }) => cell.model.metadata.nbi.chatbook;

describe('summarizeCodeCell: summary hash', () => {
  it('ties a new description to the code it describes', async () => {
    const cell = makeCell('x = 2', { mode: 'code' });
    summarizeChatbookCell.mockResolvedValue('Set x to 2');
    await summarizeCodeCell(cell as any);
    expect(meta(cell).prompt).toBe('Set x to 2');
    expect(meta(cell).summaryHash).toBe(
      await chatbookSummaryHash('Set x to 2', 'x = 2')
    );
  });

  it('keeps the old tie when a refresh fails', async () => {
    const old = await chatbookSummaryHash('Set x to 1', 'x = 1');
    const cell = makeCell('x = 2', {
      mode: 'code',
      prompt: 'Set x to 1',
      summaryHash: old
    });
    summarizeChatbookCell.mockRejectedValue(new Error('rate limited'));
    await summarizeCodeCell(cell as any, undefined, { force: true });
    expect(meta(cell).prompt).toBe('Set x to 1');
    expect(meta(cell).summaryHash).toBe(old);
  });

  it('writes nothing when the code changes during a refresh', async () => {
    const old = await chatbookSummaryHash('Set x to 1', 'x = 1');
    const cell = makeCell('x = 2', {
      mode: 'code',
      prompt: 'Set x to 1',
      summaryHash: old
    });
    summarizeChatbookCell.mockImplementation(async () => {
      cell.edit('x = 3');
      return 'Set x to 2';
    });
    await summarizeCodeCell(cell as any, undefined, { force: true });
    expect(meta(cell).prompt).toBe('Set x to 1');
    expect(meta(cell).summaryHash).toBe(old);
  });
});
