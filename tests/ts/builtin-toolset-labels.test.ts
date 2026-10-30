// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { builtinToolsetLabel } from '../../src/builtin-toolset-labels';
import { BuiltinToolsetType } from '../../src/tokens';
import { pseudoBundle } from './pseudo-translator';

describe('builtinToolsetLabel', () => {
  it.each(Object.values(BuiltinToolsetType))(
    'translates the built-in toolset %s rather than showing the server name',
    id => {
      const label = builtinToolsetLabel(pseudoBundle, {
        id,
        name: 'server name'
      });
      expect(label).not.toBe('server name');
      expect(label).toMatch(/^\[!! .+ !!\]$/);
    }
  );

  it('falls back to the server name for a toolset it does not know', () => {
    expect(
      builtinToolsetLabel(pseudoBundle, { id: 'ext-tools', name: 'Ext' })
    ).toBe('Ext');
  });
});
