// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

jest.mock('../../src/api', () => ({
  NBIAPI: {
    config: {
      tourOverrides: {
        steps: { welcome: { title: 'Welcome to ACME' } }
      },
      isInClaudeCodeMode: false,
      isInAcpMode: false,
      isClaudeCliAvailable: false,
      isCodexCliAvailable: true,
      isOpenCodeCliAvailable: true,
      isPiCliAvailable: false,
      isGitHubCopilotCliAvailable: false,
      isCodingAgentLauncherDisabledByPolicy: () => false
    }
  }
}));

import {
  getLanguageCode,
  initTranslations,
  toLanguageTag
} from '../../src/i18n';
import {
  activeTourSteps,
  formatLauncherList,
  withoutDefaultCopies
} from '../../src/tour/tour-steps';
import { tourText } from '../../src/tour/tour-text';
import { pseudo, pseudoBundle } from './pseudo-translator';

afterEach(() => initTranslations(null));

describe('language tag', () => {
  it('turns a JupyterLab locale setting into a BCP 47 tag', () => {
    expect(toLanguageTag('de_DE')).toBe('de-DE');
    expect(toLanguageTag('zh_TW')).toBe('zh-TW');
    // A legacy code Intl renames is still recognized.
    expect(toLanguageTag('iw_IL')).toBe('he-IL');
  });

  it("leaves English, unset and unusable codes to the browser's locale", () => {
    expect(toLanguageTag('')).toBeUndefined();
    expect(toLanguageTag(undefined)).toBeUndefined();
    expect(toLanguageTag('en')).toBeUndefined();
    expect(toLanguageTag('default')).toBeUndefined();
    expect(toLanguageTag('not a locale!')).toBeUndefined();
    // Crowdin's in-context pseudo-language: Intl would substitute another
    // locale rather than fail.
    expect(toLanguageTag('ach_UG')).toBeUndefined();
  });

  it('follows the bound translator', () => {
    initTranslations({ languageCode: 'fr_FR', load: () => pseudoBundle });
    expect(getLanguageCode()).toBe('fr-FR');
    initTranslations(null);
    expect(getLanguageCode()).toBeUndefined();
  });
});

describe('first-run tour under a translated locale', () => {
  it('lists launchers the way the language does', () => {
    expect(formatLauncherList(['A', 'B', 'C'], 'en')).toBe('A, B, and C');
    expect(formatLauncherList(['A', 'B', 'C'], 'de')).toBe('A, B und C');
  });

  it('translates default copy and leaves empty text alone', () => {
    expect(tourText(pseudoBundle, 'Next')).toBe(pseudo('Next'));
    expect(tourText(pseudoBundle, '')).toBe('');
  });

  it('translates the defaults but shows an admin override as written', () => {
    const steps = activeTourSteps(pseudoBundle);
    const welcome = steps.find(step => step.id === 'welcome')!;
    expect(welcome.title).toBe('Welcome to ACME');
    expect(welcome.description).toMatch(/^\[!! .+ !!\]$/);
    const launchers = steps.find(step => step.id === 'launcher-tiles')!;
    // The template is translated, then {launchers} is filled in.
    expect(launchers.description).toMatch(/^\[!! .*Codex and opencode.* !!\]$/);
  });
});

describe('admin tour overrides under a translated locale', () => {
  it("joins an admin launcher template's list in the user's language", () => {
    const { NBIAPI } = jest.requireMock('../../src/api');
    const previous = NBIAPI.config.tourOverrides;
    NBIAPI.config.tourOverrides = {
      steps: {
        'launcher-tiles': { description_plural: 'Tiles for {launchers}.' }
      }
    };
    initTranslations({ languageCode: 'de_DE', load: () => pseudoBundle });
    try {
      const launchers = activeTourSteps(pseudoBundle).find(
        step => step.id === 'launcher-tiles'
      )!;
      expect(launchers.description).toBe('Tiles for Codex und opencode.');
    } finally {
      NBIAPI.config.tourOverrides = previous;
    }
  });
});

describe('tour copy not translated yet', () => {
  it('joins the list in English when the sentence is still English', () => {
    const english = {
      ...pseudoBundle,
      _p: (_context: string, text: string) => text
    };
    initTranslations({ languageCode: 'de_DE', load: () => english });
    const launchers = activeTourSteps(english).find(
      step => step.id === 'launcher-tiles'
    )!;
    expect(launchers.description).toContain('Codex and opencode');
  });

  it('translates a copied default an admin left unchanged', () => {
    const { NBIAPI } = jest.requireMock('../../src/api');
    const previous = NBIAPI.config.tourOverrides;
    NBIAPI.config.tourOverrides = {
      ui: { next: 'Next' },
      steps: { done: { title: "You're ready" } }
    };
    try {
      expect(withoutDefaultCopies(NBIAPI.config.tourOverrides)?.ui).toEqual({});
      const done = activeTourSteps(pseudoBundle).find(
        step => step.id === 'done'
      );
      expect(done?.title).toMatch(/^\[!! .+ !!\]$/);
    } finally {
      NBIAPI.config.tourOverrides = previous;
    }
  });
});
