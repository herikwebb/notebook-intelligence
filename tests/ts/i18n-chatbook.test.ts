// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  CHATBOOK_EXECUTION_MODES,
  ChatbookExportLanguageError,
  chatbookExecutionModeSummary,
  chatbookExportLanguageMessage
} from '../../src/chatbook-core';
import {
  NotebookKernelNotFoundError,
  kernelNotFoundMessage
} from '../../src/notebook-kernels';
import { describeMCPConfigSaveError } from '../../src/mcp-config-save';
import { uploadFailureMessage } from '../../src/terminal-drag';
import { initTranslations } from '../../src/i18n';
import { pseudo, pseudoBundle, pseudoTranslator } from './pseudo-translator';

afterEach(() => initTranslations(null));

describe('Chatbook text under a translated locale', () => {
  it.each(CHATBOOK_EXECUTION_MODES)('summarizes the %s mode', mode => {
    expect(chatbookExecutionModeSummary(pseudoBundle, mode)).toMatch(
      /^\[!! .+ !!\]$/
    );
  });

  it('translates the missing-kernel message but keeps the error English', () => {
    // Created under a translated locale: the message must stay English.
    initTranslations(pseudoTranslator);
    const error = new NotebookKernelNotFoundError({ kernelName: 'ir' });
    expect(kernelNotFoundMessage(pseudoBundle, error)).toBe(
      pseudo('No installed Jupyter kernel matches kernel "ir".')
    );
    // UI tools return error.message to the model.
    expect(error.message).toBe(
      'No installed Jupyter kernel matches kernel "ir".'
    );
  });

  it('translates the reason an MCP config save failed', () => {
    initTranslations(pseudoTranslator);
    expect(describeMCPConfigSaveError({})).toBe(
      pseudo('the save failed for an unknown reason')
    );
  });

  it('puts the overflow count and the listed failures in their places', () => {
    const failures = ['a', 'b', 'c', 'd', 'e'].map(name => ({
      name,
      reason: '413'
    }));
    expect(uploadFailureMessage(pseudoBundle, failures)).toBe(
      pseudo('Terminal drop upload failed for a: 413; b: 413; c: 413 (+2 more)')
    );
    expect(uploadFailureMessage(pseudoBundle, failures.slice(0, 1))).toBe(
      pseudo('Terminal drop upload failed for a: 413')
    );
  });

  it('translates the export language error but keeps its message English', () => {
    initTranslations(pseudoTranslator);
    const error = new ChatbookExportLanguageError('cobol');
    expect(chatbookExportLanguageMessage(pseudoBundle, error)).toBe(
      pseudo(
        'Cannot export unrun Chatbook cells: no safe line comment for cobol'
      )
    );
    expect(error.message).toBe(
      'Cannot export unrun Chatbook cells: no safe line comment for cobol'
    );
  });
});
