// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

// Pure helpers extracted from `terminal-drag.ts` so they can be unit
// tested without JupyterLab / Lumino imports (which pull DOM globals
// that jsdom doesn't provide, like DragEvent).

import { shellSingleQuote } from './shell-utils';

export type DragMode = 'mention' | 'raw';

/**
 * True when `path` contains no control characters and can be pasted into
 * a terminal as inert text.
 *
 * Rejects C0 controls, DEL and C1 controls. A dropped path is typed into
 * the terminal via xterm's paste(), which rewrites every LF/CRLF to CR;
 * the tty line discipline then hands each CR to the foreground program as
 * an end-of-line, so a path carrying "\n<command>\n" would run <command>
 * as soon as it lands (mention mode is deliberately unquoted, and raw
 * mode's single quotes only protect POSIX shells, not REPLs). ESC opens
 * terminal control sequences. None of these belong in a path.
 */
export function isTerminalSafePath(path: string): boolean {
  for (let i = 0; i < path.length; i++) {
    const code = path.charCodeAt(i);
    if (code <= 0x1f || (code >= 0x7f && code <= 0x9f)) {
      return false;
    }
  }
  return true;
}

/**
 * Split dropped paths into the ones that can be pasted and the ones that
 * must be refused (see `isTerminalSafePath`).
 */
export function partitionTerminalSafePaths(paths: string[]): {
  safe: string[];
  rejected: string[];
} {
  const safe: string[] = [];
  const rejected: string[] = [];
  for (const path of paths) {
    (isTerminalSafePath(path) ? safe : rejected).push(path);
  }
  return { safe, rejected };
}

/**
 * Format a list of paths for injection per mode. @-mention prefixes each
 * path with "@" (Claude Code syntax, no quoting); raw mode shell-escapes
 * absolute paths for non-Claude shell sessions. Single-space separator
 * is intentional; the trailing space is appended by the caller.
 */
export function formatForMode(paths: string[], mode: DragMode): string {
  if (mode === 'mention') {
    return paths.map(p => `@${p}`).join(' ');
  }
  return paths.map(shellSingleQuote).join(' ');
}

export function invertMode(mode: DragMode, shouldInvert: boolean): DragMode {
  if (!shouldInvert) {
    return mode;
  }
  return mode === 'mention' ? 'raw' : 'mention';
}
