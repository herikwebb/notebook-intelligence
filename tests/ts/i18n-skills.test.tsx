// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('../../src/api', () => ({
  NBIAPI: {
    config: { allowGithubSkillImport: true, isInClaudeCodeMode: true },
    configChanged: { connect: jest.fn(), disconnect: jest.fn() },
    skillsReloaded: { connect: jest.fn(), disconnect: jest.fn() },
    listSkills: jest.fn(),
    getSkillsContext: jest.fn()
  }
}));

import { NBIAPI } from '../../src/api';
import { TranslationContext } from '../../src/i18n';
import { SettingsPanelComponentSkills } from '../../src/components/skills-panel';
import { pseudo, pseudoBundle } from './pseudo-translator';

const trackingSkill = {
  scope: 'user',
  name: 'tracker',
  description: 'Follows a GitHub repo',
  allowedTools: [],
  rootPath: '/home/u/.claude/skills/tracker',
  files: ['SKILL.md'],
  source: 'https://github.com/owner/repo',
  managed: false,
  managedSource: '',
  managedRef: '',
  tracksUpstream: true,
  trackingRef: 'abc1234def'
};

describe('Skills panel under a translated locale', () => {
  beforeEach(() => {
    (NBIAPI as any).listSkills.mockResolvedValue([trackingSkill]);
    (NBIAPI as any).getSkillsContext.mockResolvedValue({
      userSkillsDir: '/home/u/.claude/skills/',
      projectSkillsDir: '/work/.claude/skills/',
      projectName: 'work'
    });
  });

  it('renders a tracking skill with translated badges and headings', async () => {
    render(
      <TranslationContext.Provider value={pseudoBundle}>
        <SettingsPanelComponentSkills />
      </TranslationContext.Provider>
    );
    const badge = await screen.findByText(pseudo('Tracking'));
    expect(badge).toHaveAttribute(
      'title',
      pseudo(
        'Tracking upstream from https://github.com/owner/repo (last sync: abc1234)'
      )
    );
    expect(screen.getByText(pseudo('New Skill'))).toBeInTheDocument();
    expect(
      await screen.findByText(`${pseudo('USER')} · 1`)
    ).toBeInTheDocument();
    expect(
      await screen.findByText(`${pseudo(`${pseudo('PROJECT')} · work`)} · 0`)
    ).toBeInTheDocument();
  });
});
