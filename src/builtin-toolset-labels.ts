// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { TranslationBundle } from '@jupyterlab/translation';

import { BuiltinToolsetType } from './tokens';

// The server sends built-in toolset names in English; label the ones NBI ships
// by id so the tools picker reads in the user's language.
export function builtinToolsetLabel(
  trans: TranslationBundle,
  toolset: { id: string; name: string }
): string {
  switch (toolset.id) {
    case BuiltinToolsetType.NotebookEdit:
      return trans._p('toolset', 'Notebook edit');
    case BuiltinToolsetType.NotebookExecute:
      return trans._p('toolset', 'Notebook execute');
    case BuiltinToolsetType.PythonFileEdit:
      return trans._p('toolset', 'Python file edit');
    case BuiltinToolsetType.FileRead:
      return trans._p('toolset', 'File read');
    case BuiltinToolsetType.FileEdit:
      return trans._p('toolset', 'File edit');
    case BuiltinToolsetType.CommandExecute:
      return trans._p('toolset', 'Command execute');
    default:
      return toolset.name;
  }
}
