// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  CLAUDE_CONFIG_SCOPES,
  removedFromScopeConfig,
  scopeHeading,
  scopeHint,
  scopeOption
} from '../../src/components/claude-scope';
import { summarizePluginNames } from '../../src/components/plugins-panel';
import { pseudo, pseudoBundle } from './pseudo-translator';

const TRANSLATED = /^\[!! .+ !!\]$/;

describe('Claude config scope labels under a translated locale', () => {
  it.each(CLAUDE_CONFIG_SCOPES)('translates every label of %s', scope => {
    expect(scopeHeading(pseudoBundle, scope)).toMatch(TRANSLATED);
    expect(scopeHint(pseudoBundle, scope)).toMatch(TRANSLATED);
    expect(scopeOption(pseudoBundle, scope)).toMatch(TRANSLATED);
    expect(removedFromScopeConfig(pseudoBundle, 'plugin', 'p', scope)).toMatch(
      TRANSLATED
    );
    expect(
      removedFromScopeConfig(pseudoBundle, 'mcp-server', 'srv', scope)
    ).toMatch(TRANSLATED);
  });

  it('still names a scope a newer Claude CLI reports', () => {
    expect(removedFromScopeConfig(pseudoBundle, 'plugin', 'p', 'managed')).toBe(
      pseudo('"p" will be removed from Claude\'s managed-scope config.')
    );
  });

  it('names the project file when the tab gives one', () => {
    expect(scopeHint(pseudoBundle, 'project', '.mcp.json')).toBe(
      pseudo('shared via the project repo (.mcp.json)')
    );
  });
});

describe('summarizePluginNames under a translated locale', () => {
  it('translates the overflow tail', () => {
    expect(summarizePluginNames(pseudoBundle, ['a', 'b', 'c'], 2)).toBe(
      pseudo(`a${pseudo(', ')}b, +1 more`)
    );
  });
});
