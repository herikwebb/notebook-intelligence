// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { TranslationBundle } from '@jupyterlab/translation';

/**
 * Translate a default tour string from tour-defaults.json. That file stays
 * the English source (it doubles as the admin override template), and
 * scripts/i18n.py extracts its strings under these same contexts
 * (TOUR_CONTEXT and TOUR_TEMPLATE_CONTEXT there). Admin overrides are shown
 * as written and never pass through here.
 */
export function tourText(trans: TranslationBundle, text: string): string {
  if (!text) {
    return text;
  }
  // The launcher templates carry a token and a Launcher category name that
  // a translator must leave alone; their context says so.
  return text.includes('{launchers}')
    ? // eslint-disable-next-line no-restricted-syntax -- the msgids are extracted from tour-defaults.json
      trans._p(
        "first-run tour; keep {launchers} as written, and 'Coding Agent' as JupyterLab's Launcher names it",
        text
      )
    : // eslint-disable-next-line no-restricted-syntax -- the msgids are extracted from tour-defaults.json
      trans._p('first-run tour', text);
}
