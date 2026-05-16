// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { CommandIDs } from './command-ids';

// Cell-targeting commands accept an optional `notebookPath` to bypass
// `app.shell.currentWidget`. When the agent runs a task and the user
// switches tabs mid-run, the previously-active notebook is no longer the
// focused widget; the chat sidebar injects the captured task-target path
// into args for these command IDs so cell ops resolve against the right
// notebook (issue #252). Built from `CommandIDs` so a rename on either
// side is caught at compile time.
export const NOTEBOOK_TARGETED_COMMAND_IDS: ReadonlySet<string> = new Set([
  CommandIDs.addMarkdownCellToActiveNotebook,
  CommandIDs.addCodeCellToActiveNotebook,
  CommandIDs.getCellTypeAndSource,
  CommandIDs.setCellTypeAndSource,
  CommandIDs.getNumberOfCells,
  CommandIDs.getCellOutput,
  CommandIDs.insertCellAtIndex,
  CommandIDs.deleteCellAtIndex,
  CommandIDs.runCellAtIndex
]);

export function injectTaskTargetNotebook(
  commandId: string,
  args: Record<string, unknown> | undefined,
  taskTargetPath: string | null
): Record<string, unknown> | undefined {
  if (
    !taskTargetPath ||
    !NOTEBOOK_TARGETED_COMMAND_IDS.has(commandId) ||
    (args && args.notebookPath)
  ) {
    return args;
  }
  return { ...(args ?? {}), notebookPath: taskTargetPath };
}
