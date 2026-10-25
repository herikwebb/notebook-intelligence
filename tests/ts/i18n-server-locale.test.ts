// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { withLocale } from '../../src/handler';
import {
  getCatalogLocale,
  getTextDirection,
  initTranslations
} from '../../src/i18n';
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

describe('panel direction', () => {
  // A catalog declares its direction by translating this token.
  const declaring = (direction: string) => ({
    ...pseudoBundle,
    _p: (context: string, text: string) =>
      context.startsWith('text direction') ? direction : text
  });

  it("follows the direction the language's catalog declares", () => {
    expect(getTextDirection()).toBe('ltr');
    initTranslations({ languageCode: 'he_IL', load: () => declaring('rtl') });
    expect(getTextDirection()).toBe('rtl');
    initTranslations({ languageCode: 'de-DE', load: () => declaring('ltr') });
    expect(getTextDirection()).toBe('ltr');
  });

  it('stays left to right in a language NBI has no catalog for', () => {
    // An untranslated token comes back as its English msgid, "ltr".
    const english = { ...pseudoBundle, _p: (_c: string, text: string) => text };
    initTranslations({ languageCode: 'fa-IR', load: () => english });
    expect(getTextDirection()).toBe('ltr');
  });
});
