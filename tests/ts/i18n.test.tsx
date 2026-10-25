// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { render, screen } from '@testing-library/react';

import {
  getTrans,
  initTranslations,
  interpolate,
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
    const trans = getTrans();
    expect(trans.__('Failed to find notebook: %1', 'a.ipynb')).toBe(
      'Failed to find notebook: a.ipynb'
    );
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('using English'));
    warn.mockRestore();
  });

  it('falls back to English when the translator goes away', () => {
    initTranslations(pseudoTranslator);
    initTranslations(null);
    const trans = getTrans();
    expect(trans.__('Close')).toBe('Close');
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

describe('interpolate', () => {
  it('places elements where the translated sentence puts them', () => {
    initTranslations(pseudoTranslator);
    const trans = getTrans();
    render(
      <p data-testid="sentence">
        {interpolate(
          (first, second) => trans.__('Read %2 before %1.', first, second),
          <a href="#a">A</a>,
          <b>B</b>
        )}
      </p>
    );
    const sentence = screen.getByTestId('sentence');
    expect(sentence.textContent).toBe(pseudo('Read B before A.'));
    expect(sentence.querySelector('b')?.textContent).toBe('B');
    expect(sentence.querySelector('a')?.textContent).toBe('A');
  });

  it('keeps an element whose placeholder the translation leaves out', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      const { rerender } = render(
        <p data-testid="sentence">
          {interpolate(() => 'Enter the code.', <b>ABCD-1234</b>)}
        </p>
      );
      const sentence = screen.getByTestId('sentence');
      expect(sentence.textContent).toBe('Enter the code. ABCD-1234');
      rerender(
        <p data-testid="sentence">
          {interpolate(() => 'Enter the code.', <b>ABCD-1234</b>)}
        </p>
      );
      expect(warn).toHaveBeenCalledTimes(1);
      expect(warn).toHaveBeenCalledWith(
        expect.stringContaining('"Enter the code." leaves out placeholder %1')
      );
    } finally {
      warn.mockRestore();
    }
  });
});
