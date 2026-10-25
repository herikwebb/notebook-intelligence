// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  ITranslator,
  nullTranslator,
  TranslationBundle
} from '@jupyterlab/translation';

const english = nullTranslator.load('notebook_intelligence');

/** Marks a translated string so a test can tell it went through a bundle. */
export function pseudo(text: string): string {
  return `[!! ${text} !!]`;
}

/**
 * A bundle that wraps every string in `[!! … !!]` after formatting it the way
 * the English bundle does. A string a test finds without the marks was never
 * passed through `trans`.
 */
export const pseudoBundle: TranslationBundle = {
  __: (msgid, ...args) => pseudo(english.__(msgid, ...args)),
  _n: (msgid, plural, n, ...args) =>
    pseudo(english._n(msgid, plural, n, ...args)),
  _p: (msgctxt, msgid, ...args) => pseudo(english._p(msgctxt, msgid, ...args)),
  _np: (msgctxt, msgid, plural, n, ...args) =>
    pseudo(english._np(msgctxt, msgid, plural, n, ...args)),
  gettext: (msgid, ...args) => pseudo(english.gettext(msgid, ...args)),
  ngettext: (msgid, plural, n, ...args) =>
    pseudo(english.ngettext(msgid, plural, n, ...args)),
  pgettext: (msgctxt, msgid, ...args) =>
    pseudo(english.pgettext(msgctxt, msgid, ...args)),
  npgettext: (msgctxt, msgid, plural, n, ...args) =>
    pseudo(english.npgettext(msgctxt, msgid, plural, n, ...args)),
  dcnpgettext: (domain, msgctxt, msgid, plural, n, ...args) =>
    pseudo(english.dcnpgettext(domain, msgctxt, msgid, plural, n, ...args))
};

export const pseudoTranslator: ITranslator = {
  languageCode: 'xx-XX',
  load: () => pseudoBundle
};
