// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

jest.mock('../../src/handler', () => ({
  requestAPI: jest.fn()
}));

import { requestAPI } from '../../src/handler';
import { TranslationContext } from '../../src/i18n';
import {
  ReadinessCard,
  _resetReadinessCacheForTests
} from '../../src/components/readiness-card';
import {
  ModelPropertyField,
  SETTINGS_TABS,
  SettingsPanelTabsComponent
} from '../../src/components/settings-panel';
import {
  lockedByEnvironmentTip,
  lockedTip,
  optionalLabel
} from '../../src/components/setting-lock';
import { pseudo, pseudoBundle } from './pseudo-translator';

function renderTranslated(element: React.ReactElement) {
  return render(
    <TranslationContext.Provider value={pseudoBundle}>
      {element}
    </TranslationContext.Provider>
  );
}

describe('settings components under a translated locale', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    _resetReadinessCacheForTests();
  });

  it('translates the readiness verdict, group and level, not server text', async () => {
    (requestAPI as jest.Mock).mockResolvedValueOnce({
      schema_version: 1,
      generated_at: '2026-10-24T00:00:00Z',
      verdict: 'not_ready',
      headline: 'Server headline',
      checks: [
        {
          id: 'claude.cli',
          group: 'claude',
          level: 'blocked',
          title: 'Claude Code CLI',
          detail: 'The claude CLI was not found.'
        }
      ]
    });
    renderTranslated(<ReadinessCard />);
    await screen.findByText(pseudo('Not ready'));
    expect(screen.getByText(pseudo('Claude mode'))).toBeInTheDocument();
    expect(screen.getByText(pseudo('blocked'))).toBeInTheDocument();
    // Server-written text arrives as is; phase 7 translates it on the server.
    expect(screen.getByText('Server headline')).toBeInTheDocument();
  });

  it('marks a required property field through the bundle', () => {
    renderTranslated(
      <ModelPropertyField
        property={{ id: 'm', name: 'Model', description: '', value: '' }}
        inputName="m"
        onChange={() => undefined}
      />
    );
    fireEvent.blur(screen.getByRole('textbox'));
    expect(screen.getByText(pseudo('Model is required.'))).toBeInTheDocument();
  });

  it('translates every shipped tab label except product names', () => {
    const productNames = new Set(['claude', 'acp', 'claude-mcp']);
    for (const tab of SETTINGS_TABS) {
      const label = tab.label(pseudoBundle);
      if (productNames.has(tab.id)) {
        expect(label).not.toMatch(/^\[!! /);
      } else {
        expect(label).toMatch(/^\[!! .+ !!\]$/);
      }
    }
  });

  it('translates tab labels when the tabs render', () => {
    renderTranslated(
      <SettingsPanelTabsComponent
        tabs={[
          {
            id: 'general',
            label: trans => trans._p('settings tab', 'General'),
            visible: () => true,
            render: () => <div />
          }
        ]}
        activeTab="general"
        onTabSelected={() => undefined}
      />
    );
    expect(
      screen.getByRole('tab', { name: pseudo('General') })
    ).toBeInTheDocument();
  });

  it('gives a locked setting a translated reason and an unlocked one none', () => {
    expect(lockedTip(pseudoBundle, true)).toBe(
      pseudo('Locked by your administrator')
    );
    expect(lockedTip(pseudoBundle, false)).toBe('');
    expect(lockedByEnvironmentTip(pseudoBundle, 'OPENAI_API_KEY')).toBe(
      pseudo('Locked by OPENAI_API_KEY')
    );
    expect(optionalLabel(pseudoBundle, 'API Key')).toBe(
      pseudo('API Key (optional)')
    );
  });
});
