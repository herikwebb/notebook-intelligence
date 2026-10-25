// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { withLocale } from '../../src/handler';
import { getCatalogLocale, initTranslations } from '../../src/i18n';
import { pseudoBundle } from './pseudo-translator';

afterEach(() => initTranslations(null));

describe('the language the server writes in', () => {
  it("is JupyterLab's own code, independent of Intl", () => {
    initTranslations({ languageCode: 'de-DE', load: () => pseudoBundle });
    expect(getCatalogLocale()).toBe('de-DE');
    initTranslations({ languageCode: 'ach_UG', load: () => pseudoBundle });
    expect(getCatalogLocale()).toBe('ach_UG');
    initTranslations({ languageCode: 'en', load: () => pseudoBundle });
    expect(getCatalogLocale()).toBeUndefined();
  });

  it('goes with server URLs as a query parameter', () => {
    initTranslations({ languageCode: 'de-DE', load: () => pseudoBundle });
    expect(withLocale('http://h/notebook-intelligence/config')).toBe(
      'http://h/notebook-intelligence/config?nbi_locale=de-DE'
    );
    expect(withLocale('ws://h/copilot?x=1')).toBe(
      'ws://h/copilot?x=1&nbi_locale=de-DE'
    );
  });

  it('is left out in English', () => {
    expect(withLocale('http://h/config')).toBe('http://h/config');
  });
});
