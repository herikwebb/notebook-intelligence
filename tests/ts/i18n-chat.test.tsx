// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { TranslationContext } from '../../src/i18n';
import { ToolCallGroup } from '../../src/components/tool-call-group';
import { ToolCallCard } from '../../src/components/tool-call-card';
import { PermissionModeSelect } from '../../src/components/permission-mode-select';
import { SafeAnchor } from '../../src/components/safe-anchor';
import { pseudo, pseudoBundle } from './pseudo-translator';

function renderTranslated(element: React.ReactElement) {
  return render(
    <TranslationContext.Provider value={pseudoBundle}>
      {element}
    </TranslationContext.Provider>
  );
}

function calls(n: number, failed = 0) {
  return Array.from({ length: n }, (_, i) => ({
    id: `t${i}`,
    title: `Tool ${i}`,
    kind: 'read',
    status: i < failed ? 'failed' : 'completed'
  }));
}

describe('chat components under a translated locale', () => {
  it('pluralizes each count in the tool call summary on its own', () => {
    renderTranslated(<ToolCallGroup toolCalls={calls(3, 1)} />);
    expect(
      screen.getByText(
        pseudo(`${pseudo('3 tool calls')} (${pseudo('1 failed')})`)
      )
    ).toBeVisible();
  });

  it('translates a tool call status and its diff toggle', () => {
    renderTranslated(
      <ToolCallCard
        toolCall={{
          id: 'a',
          title: 'Edit',
          kind: 'edit',
          status: 'in_progress',
          diffs: [{ path: 'a.py', lines: [{ type: 'add', content: 'x' }] }]
        }}
      />
    );
    expect(screen.getByText(pseudo('in progress'))).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: pseudo('Hide diff') })
    ).toBeInTheDocument();
  });

  it('translates permission mode labels when the menu renders', () => {
    renderTranslated(
      <PermissionModeSelect
        value="plan"
        bypassAllowed={false}
        onModeChange={() => {}}
      />
    );
    const button = screen.getByRole('button', {
      name: pseudo(`Permission mode: ${pseudo('Plan')}`)
    });
    fireEvent.click(button);
    expect(
      screen.getByRole('menuitemradio', { name: pseudo('Accept Edits') })
    ).toBeInTheDocument();
  });

  it('translates the screen-reader suffix of an external link', () => {
    renderTranslated(<SafeAnchor href="https://example.com">site</SafeAnchor>);
    expect(screen.getByText(pseudo('(opens in new tab)'))).toBeInTheDocument();
  });
});
