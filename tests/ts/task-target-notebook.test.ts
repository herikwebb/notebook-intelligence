// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { CommandIDs } from '../../src/command-ids';
import {
  NOTEBOOK_TARGETED_COMMAND_IDS,
  injectTaskTargetNotebook
} from '../../src/task-target-notebook';

const RUN_CELL = CommandIDs.runCellAtIndex;
const NON_NOTEBOOK = CommandIDs.runCommandInTerminal;

describe('injectTaskTargetNotebook', () => {
  it('injects notebookPath when command is notebook-targeted and path is set', () => {
    const result = injectTaskTargetNotebook(
      RUN_CELL,
      { cellIndex: 3 },
      'project/foo.ipynb'
    );
    expect(result).toEqual({
      cellIndex: 3,
      notebookPath: 'project/foo.ipynb'
    });
  });

  it('returns args unchanged when no task-target path is set', () => {
    const args = { cellIndex: 1 };
    const result = injectTaskTargetNotebook(RUN_CELL, args, null);
    // Same reference: no unnecessary clone when nothing to inject.
    expect(result).toBe(args);
  });

  it('returns args unchanged when command is not notebook-targeted', () => {
    const args = { command: 'ls' };
    const result = injectTaskTargetNotebook(
      NON_NOTEBOOK,
      args,
      'project/foo.ipynb'
    );
    expect(result).toBe(args);
  });

  it('preserves caller-supplied notebookPath rather than overriding it', () => {
    // If the backend explicitly passes a notebook path the frontend
    // should defer to it. Otherwise tools that genuinely want to target
    // a non-active notebook can't.
    const args = { cellIndex: 0, notebookPath: 'other/bar.ipynb' };
    const result = injectTaskTargetNotebook(
      RUN_CELL,
      args,
      'project/foo.ipynb'
    );
    expect(result).toBe(args);
    expect((result as { notebookPath: string }).notebookPath).toBe(
      'other/bar.ipynb'
    );
  });

  it('handles undefined args by returning a fresh object with the path', () => {
    const result = injectTaskTargetNotebook(
      RUN_CELL,
      undefined,
      'project/foo.ipynb'
    );
    expect(result).toEqual({ notebookPath: 'project/foo.ipynb' });
  });

  it('does not mutate the input args', () => {
    const args = { cellIndex: 7 };
    injectTaskTargetNotebook(RUN_CELL, args, 'project/foo.ipynb');
    expect(args).toEqual({ cellIndex: 7 });
  });
});

describe('NOTEBOOK_TARGETED_COMMAND_IDS', () => {
  it('covers every cell-targeting RunUICommand in the backend toolset', () => {
    // The set is the single source of truth on the frontend for "this
    // command needs notebookPath injection". Each entry below has a
    // corresponding `await response.run_ui_command(...)` call in
    // notebook_intelligence/built_in_toolsets.py or claude.py — if a new
    // cell-targeting tool lands without an entry here, the agent's calls
    // will regress to currentWidget-based resolution and fail when the
    // user switches tabs (issue #252).
    expect(NOTEBOOK_TARGETED_COMMAND_IDS.has(CommandIDs.runCellAtIndex)).toBe(
      true
    );
    expect(
      NOTEBOOK_TARGETED_COMMAND_IDS.has(CommandIDs.addCodeCellToActiveNotebook)
    ).toBe(true);
    expect(
      NOTEBOOK_TARGETED_COMMAND_IDS.has(CommandIDs.setCellTypeAndSource)
    ).toBe(true);
    // Negative spot check — a non-notebook command must not be in the set
    // so we don't inject notebookPath where the command would treat it as
    // a stray arg.
    expect(
      NOTEBOOK_TARGETED_COMMAND_IDS.has(CommandIDs.runCommandInTerminal)
    ).toBe(false);
  });
});
