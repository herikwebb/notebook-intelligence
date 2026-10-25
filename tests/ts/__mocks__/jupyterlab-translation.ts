// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

// Stub for @jupyterlab/translation, whose ESM build jest's CommonJS pipeline
// can't load. Reproduces its English bundle: the msgid (or the plural form
// for n !== 1) with %1, %2 ... replaced and %% kept as a literal %.

function strfmt(fmt: string, ...args: any[]): string {
  return fmt
    .replace(/%%/g, '%% ')
    .replace(/%(\d+)/g, (_match, index) => args[Number(index) - 1])
    .replace(/%% /g, '%');
}

function ngettext(
  msgid: string,
  msgidPlural: string,
  n: number,
  ...args: any[]
): string {
  return strfmt(n === 1 ? msgid : msgidPlural, ...[n].concat(args));
}

const englishBundle = {
  __: (msgid: string, ...args: any[]) => strfmt(msgid, ...args),
  _n: ngettext,
  _p: (_msgctxt: string, msgid: string, ...args: any[]) =>
    strfmt(msgid, ...args),
  _np: (
    _msgctxt: string,
    msgid: string,
    plural: string,
    n: number,
    ...args: any[]
  ) => ngettext(msgid, plural, n, ...args),
  gettext: (msgid: string, ...args: any[]) => strfmt(msgid, ...args),
  ngettext,
  pgettext: (_msgctxt: string, msgid: string, ...args: any[]) =>
    strfmt(msgid, ...args),
  npgettext: (
    _msgctxt: string,
    msgid: string,
    plural: string,
    n: number,
    ...args: any[]
  ) => ngettext(msgid, plural, n, ...args),
  dcnpgettext: (
    _domain: string,
    _msgctxt: string,
    msgid: string,
    plural: string,
    n: number,
    ...args: any[]
  ) => ngettext(msgid, plural, n, ...args)
};

export const nullTranslator = {
  languageCode: 'en',
  load: (_domain: string) => englishBundle
};

export const ITranslator = { name: '@jupyterlab/translation:ITranslator' };
