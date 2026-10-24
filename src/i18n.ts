// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
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

/**
 * Bind NBI's strings to JupyterLab's translator. Called once when the plugin
 * activates; until then (and without a translator) strings stay English.
 */
export function initTranslations(
  translator: ITranslator | null | undefined
): void {
  try {
    bundle = (translator ?? nullTranslator).load(TRANSLATION_DOMAIN);
  } catch (error) {
    // A catalog JupyterLab cannot load must not stop NBI from activating.
    console.warn(
      `Notebook Intelligence translations failed to load; using English: ${error}`
    );
    bundle = nullTranslator.load(TRANSLATION_DOMAIN);
  }
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
