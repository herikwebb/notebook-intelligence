// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { render, screen } from '@testing-library/react';

import {
  getTrans,
  initTranslations,
  TranslationContext,
  TRANSLATION_DOMAIN,
  useTrans
} from '../../src/i18n';
import { formatRevertNotification } from '../../src/open-file-refresh-watcher';
import { pseudo, pseudoBundle, pseudoTranslator } from './pseudo-translator';

afterEach(() => initTranslations(null));

describe('i18n', () => {
  it('is English, with placeholders filled in, until a translator is bound', () => {
    const trans = getTrans();
    expect(trans.__('Failed to find notebook: %1', 'a.ipynb')).toBe(
      'Failed to find notebook: a.ipynb'
    );
  });

  it('loads the notebook_intelligence domain from the bound translator', () => {
    const load = jest.fn(() => pseudoBundle);
    initTranslations({ languageCode: 'de-DE', load });
    expect(load).toHaveBeenCalledWith(TRANSLATION_DOMAIN);
    expect(TRANSLATION_DOMAIN).toBe('notebook_intelligence');
    expect(getTrans()).toBe(pseudoBundle);
  });

  it('stays English when JupyterLab cannot load the catalog', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    initTranslations({
      languageCode: 'fr-FR',
      load: () => {
        throw new Error('Wrong jsonData');
      }
    });
    expect(getTrans().__('Failed to find notebook: %1', 'a.ipynb')).toBe(
      'Failed to find notebook: a.ipynb'
    );
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('using English'));
    warn.mockRestore();
  });

  it('falls back to English when the translator goes away', () => {
    initTranslations(pseudoTranslator);
    initTranslations(null);
    expect(getTrans().__('Close')).toBe('Close');
  });

  it('translates strings built outside React through the bound bundle', () => {
    initTranslations(pseudoTranslator);
    expect(formatRevertNotification('work/a.py')).toBe(
      pseudo('work/a.py changed on disk and was reloaded')
    );
  });

  it('gives components the provided bundle, else the plugin bundle', () => {
    const Label = () => {
      const trans = useTrans();
      return <span>{trans.__('Close')}</span>;
    };
    const { unmount } = render(<Label />);
    expect(screen.getByText('Close')).toBeInTheDocument();
    unmount();

    render(
      <TranslationContext.Provider value={pseudoBundle}>
        <Label />
      </TranslationContext.Provider>
    );
    expect(screen.getByText(pseudo('Close'))).toBeInTheDocument();
  });
});
