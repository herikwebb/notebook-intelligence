// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { TranslationBundle } from '@jupyterlab/translation';
import { PluginScope } from '../api';

// The scopes of Claude Code's own configuration, shared by the Plugins and
// Claude MCP tabs (api.ts's PluginScope and ClaudeMCPScope are this union).
export type ClaudeConfigScope = PluginScope;

export const CLAUDE_CONFIG_SCOPES: readonly ClaudeConfigScope[] = [
  'user',
  'project',
  'local'
];

// Each switch is exhaustive, so a scope added to the union fails to compile
// until it has its wording. Only the removal sentence also has a runtime
// fallback: it receives the scope the Claude CLI reports for an entry, which
// a newer CLI may extend (the lists file such entries under USER).

/** The section heading for a scope's list. */
export function scopeHeading(
  trans: TranslationBundle,
  scope: ClaudeConfigScope
): string {
  switch (scope) {
    case 'user':
      return trans._p('Claude config scope heading', 'USER');
    case 'project':
      return trans._p('Claude config scope heading', 'PROJECT');
    case 'local':
      return trans._p('Claude config scope heading', 'LOCAL');
    default: {
      const unknownScope: never = scope;
      return String(unknownScope).toUpperCase();
    }
  }
}

/**
 * What a scope means. The Claude MCP tab names the project file the project
 * scope writes (`.mcp.json`).
 */
export function scopeHint(
  trans: TranslationBundle,
  scope: ClaudeConfigScope,
  projectFile?: string
): string {
  switch (scope) {
    case 'user':
      return trans.__('available in all your projects');
    case 'project':
      return projectFile
        ? trans.__('shared via the project repo (%1)', projectFile)
        : trans.__('shared via the project repo');
    case 'local':
      return trans.__('this project, this user only');
    default: {
      const unknownScope: never = scope;
      return String(unknownScope);
    }
  }
}

/** A scope picker option: the scope id Claude uses, then what it means. */
export function scopeOption(
  trans: TranslationBundle,
  scope: ClaudeConfigScope,
  projectFile?: string
): string {
  return trans._p(
    'scope picker option: %1 is the scope id, %2 what it means',
    '%1: %2',
    scope,
    scopeHint(trans, scope, projectFile)
  );
}

/** What is being removed: the noun's gender can change the sentence. */
export type ClaudeConfigEntryKind = 'plugin' | 'mcp-server';

/** The confirmation body for removing an entry from a scope's config. */
export function removedFromScopeConfig(
  trans: TranslationBundle,
  kind: ClaudeConfigEntryKind,
  name: string,
  scope: string
): string {
  if (kind === 'plugin') {
    switch (scope) {
      case 'user':
        return trans._p(
          'removing a plugin',
          '"%1" will be removed from Claude\'s user-scope config.',
          name
        );
      case 'project':
        return trans._p(
          'removing a plugin',
          '"%1" will be removed from Claude\'s project-scope config.',
          name
        );
      case 'local':
        return trans._p(
          'removing a plugin',
          '"%1" will be removed from Claude\'s local-scope config.',
          name
        );
      default:
        return trans._p(
          'removing a plugin; %2 is a scope name',
          '"%1" will be removed from Claude\'s %2-scope config.',
          name,
          scope
        );
    }
  }
  switch (scope) {
    case 'user':
      return trans._p(
        'removing an MCP server',
        '"%1" will be removed from Claude\'s user-scope config.',
        name
      );
    case 'project':
      return trans._p(
        'removing an MCP server',
        '"%1" will be removed from Claude\'s project-scope config.',
        name
      );
    case 'local':
      return trans._p(
        'removing an MCP server',
        '"%1" will be removed from Claude\'s local-scope config.',
        name
      );
    default:
      return trans._p(
        'removing an MCP server; %2 is a scope name',
        '"%1" will be removed from Claude\'s %2-scope config.',
        name,
        scope
      );
  }
}
