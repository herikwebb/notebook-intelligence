// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { Dialog } from '@jupyterlab/apputils';
import {
  ITranslator,
  nullTranslator,
  TranslationBundle
} from '@jupyterlab/translation';

/**
 * The gettext domain of NBI's catalogs: the Python package name, which is
 * the name `jupyterlab_server` serves the extension's translations under.
 */
export const TRANSLATION_DOMAIN = 'notebook_intelligence';

let bundle: TranslationBundle = nullTranslator.load(TRANSLATION_DOMAIN);
let languageCode: string | undefined;
let catalogLocale: string | undefined;
let textDirection: 'rtl' | 'ltr' = 'ltr';

/**
 * JupyterLab's language as a BCP 47 tag for Intl, or undefined to use the
 * browser's own locale. JupyterLab reports a locale setting (`de_DE`);
 * Intl wants `de-DE`. Plain English, JupyterLab's default, maps to
 * undefined so an en-GB or de-DE browser keeps its date and number style,
 * and so does a language Intl does not support here (rather than whatever
 * locale Intl would silently substitute).
 */
export function toLanguageTag(
  code: string | null | undefined
): string | undefined {
  const tag = (code ?? '').trim().replace(/_/g, '-');
  if (!tag || tag === 'default' || tag.toLowerCase() === 'en') {
    return undefined;
  }
  try {
    // Canonical first, so a legacy code (tl, iw, in) is compared with what
    // Intl turns it into (fil, he, id). getCanonicalLocales is newer than
    // this project's TypeScript lib target.
    const canonical: string = (Intl as any).getCanonicalLocales(tag)[0];
    const resolved = new Intl.NumberFormat(canonical).resolvedOptions().locale;
    const language = (part: string) => part.split('-')[0].toLowerCase();
    return language(resolved) === language(canonical) ? resolved : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Bind NBI's strings to JupyterLab's translator. Called once when the plugin
 * activates; until then (and without a translator) strings stay English.
 */
export function initTranslations(
  translator: ITranslator | null | undefined
): void {
  try {
    bundle = (translator ?? nullTranslator).load(TRANSLATION_DOMAIN);
    languageCode = toLanguageTag(translator?.languageCode);
    catalogLocale = serverLocale(translator?.languageCode);
    // Each catalog declares its direction by translating this token, the
    // usual gettext way, so a language NBI has no catalog for (whose text
    // is English) stays left to right.
    const trans = bundle;
    textDirection =
      trans._p(
        "text direction: translate as 'rtl' for a right-to-left language, otherwise 'ltr'",
        'ltr'
      ) === 'rtl'
        ? 'rtl'
        : 'ltr';
  } catch (error) {
    // A catalog JupyterLab cannot load must not stop NBI from activating.
    console.warn(
      `Notebook Intelligence translations failed to load; using English: ${error}`
    );
    bundle = nullTranslator.load(TRANSLATION_DOMAIN);
    languageCode = undefined;
    catalogLocale = undefined;
    textDirection = 'ltr';
  }
}

/**
 * JupyterLab's language as a BCP 47 tag for Intl formatting, or undefined
 * when the browser's locale should be used (see toLanguageTag).
 */
export function getLanguageCode(): string | undefined {
  return languageCode;
}

function serverLocale(code: string | undefined): string | undefined {
  const value = (code ?? '').trim();
  return !value || value === 'default' || value.toLowerCase() === 'en'
    ? undefined
    : value;
}

/**
 * JupyterLab's language as its translator reports it (de-DE; the server
 * maps it to its de_DE catalog), for the server to translate the text it
 * sends; undefined in English. Unlike getLanguageCode it does not depend on
 * Intl supporting the language.
 */
export function getCatalogLocale(): string | undefined {
  return catalogLocale;
}

/**
 * The direction NBI's own panels are laid out in. JupyterLab leaves the page
 * left to right in every language, so an Arabic or Hebrew sentence with a
 * Latin name in it would display out of order; NBI's panels and dialogs set
 * this on their root instead, and their styles use logical properties, which
 * follow it. Chat text takes its own direction per block (dir="auto" in
 * markdown-renderer.tsx).
 */
export function getTextDirection(): 'rtl' | 'ltr' {
  return textDirection;
}

/**
 * Dialog options that lay the dialog out in NBI's text direction. JupyterLab's
 * dialogs are left to right, so in Arabic or Hebrew a sentence with a Latin
 * name in it would display out of order. Only the renderer changes: its
 * header, body and footer carry dir, while the title and body stay as given,
 * so JupyterLab still treats a string title and body as strings (close
 * button, compact width, accessible name). Left to right, the options come
 * back unchanged.
 */
export function withTextDirection<T extends object>(options: T): T {
  const dir = getTextDirection();
  if (dir === 'ltr') {
    return options;
  }
  return { ...options, renderer: rtlDialogRenderer() };
}

type Rendered = ReturnType<Dialog.Renderer['createBody']>;
let rtlRenderer: Dialog.IRenderer | undefined;

/**
 * JupyterLab's dialog renderer with dir="rtl" on what it renders. Built on
 * first use, since a test's partial mock of @jupyterlab/apputils may not
 * have Dialog.Renderer, and kept, as every dialog in a session shares it.
 */
function rtlDialogRenderer(): Dialog.IRenderer {
  if (!rtlRenderer) {
    const directed = (widget: Rendered): Rendered => {
      widget.node.dir = 'rtl';
      return widget;
    };
    class DirectedRenderer extends Dialog.Renderer {
      createHeader<U>(
        title: Dialog.Header,
        reject?: () => void,
        options?: Partial<Dialog.IOptions<U>>
      ): Rendered {
        return directed(super.createHeader(title, reject, options));
      }
      createBody(value: Dialog.Body<any>): Rendered {
        return directed(super.createBody(value));
      }
      createFooter(
        buttons: ReadonlyArray<HTMLElement>,
        checkbox: HTMLElement | null
      ): Rendered {
        return directed(super.createFooter(buttons, checkbox));
      }
    }
    rtlRenderer = new DirectedRenderer();
  }
  return rtlRenderer;
}

/**
 * The bundle NBI's strings are translated with. Read it where the string is
 * used, never at module load: a bundle taken before activation is English.
 * Name the local `trans` so `jupyterlab-translate` extracts the call.
 */
export function getTrans(): TranslationBundle {
  return bundle;
}

/**
 * Supplies a bundle to React components. Without a provider, components use
 * the plugin's bundle; tests provide a pseudo-locale bundle through it.
 */
export const TranslationContext = React.createContext<TranslationBundle | null>(
  null
);

export function useTrans(): TranslationBundle {
  return React.useContext(TranslationContext) ?? getTrans();
}

/**
 * Translate a sentence with React elements (links, emphasis) inside it, so a
 * translator sees and can reorder the whole sentence. `format` receives one
 * marker per element and passes them on as the %1, %2 ... arguments:
 *
 *   interpolate(
 *     link => trans.__('Please review the %1.', link),
 *     <SafeAnchor href={url}>{trans.__('Privacy Statement')}</SafeAnchor>
 *   )
 */
// Each broken translation is reported once, not on every render.
const reportedMissingPlaceholders = new Set<string>();

export function interpolate(
  format: (...markers: string[]) => string,
  ...elements: React.ReactNode[]
): React.ReactNode[] {
  // Private-use code points, which no translation contains.
  const markers = elements.map((_, index) => `\uE000${index}\uE001`);
  const sentence = format(...markers);
  const parts = sentence.split(/\uE000(\d+)\uE001/);
  const placed = new Set<number>();
  const nodes: React.ReactNode[] = parts.map((part, index) => {
    if (index % 2 === 0) {
      return part;
    }
    placed.add(Number(part));
    return React.createElement(
      React.Fragment,
      { key: `element-${index}` },
      elements[Number(part)]
    );
  });
  // A translation that drops a placeholder would otherwise drop a link or a
  // control (the Copilot device code) with it; keep it, after the sentence.
  elements.forEach((element, index) => {
    if (!placed.has(index)) {
      const report = `${index}:${sentence}`;
      if (!reportedMissingPlaceholders.has(report)) {
        reportedMissingPlaceholders.add(report);
        console.warn(
          `Notebook Intelligence: the translation "${sentence.replace(/\uE000(\d+)\uE001/g, (_, n) => `%${Number(n) + 1}`)}" leaves out placeholder %${index + 1}`
        );
      }
      nodes.push(
        ' ',
        React.createElement(
          React.Fragment,
          { key: `missing-${index}` },
          element
        )
      );
    }
  });
  return nodes.filter(part => part !== '');
}

const numberFormats = new Map<string, Intl.NumberFormat>();

/**
 * A number in JupyterLab's language (its digits and decimal separator), or
 * in English when JupyterLab is in English: the text around it is English
 * then, whatever the browser's locale. No digit grouping, so English output
 * matches plain toFixed. Rounded with toFixed first (Intl rounds halfway
 * cases from the decimal string), and adding 0 turns a rounded -0 into 0.
 * Formatters are cached; tables format hundreds of values per render.
 */
export function formatNumber(value: number, fractionDigits: number): string {
  const locale = getLanguageCode() ?? 'en';
  const key = `${locale}|${fractionDigits}`;
  let format = numberFormats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
      useGrouping: false
    });
    numberFormats.set(key, format);
  }
  return format.format(Number(value.toFixed(fractionDigits)) + 0);
}
