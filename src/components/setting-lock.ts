// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { TranslationBundle } from '@jupyterlab/translation';

/** The tooltip for a setting an administrator pinned; empty when unlocked. */
export function lockedTip(trans: TranslationBundle, locked: boolean): string {
  return locked ? trans.__('Locked by your administrator') : '';
}

/** The placeholder of a field an environment variable pins. */
export function lockedByEnvironmentTip(
  trans: TranslationBundle,
  variable: string
): string {
  return trans._p(
    'lock reason: %1 is an environment variable name',
    'Locked by %1',
    variable
  );
}

/** A field label marked optional, worded the same everywhere. */
export function optionalLabel(trans: TranslationBundle, label: string): string {
  return trans.__('%1 (optional)', label);
}
