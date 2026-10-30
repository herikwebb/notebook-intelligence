import { expect, galata, test } from '@jupyterlab/galata';
import type { APIRequestContext } from '@playwright/test';

import { openChatSidebar } from './helpers';

/**
 * Switch JupyterLab to German and walk NBI's main surfaces, checking each
 * shows the text NBI's de_DE catalog gives it (read from what the server
 * serves, so the test does not pin any particular wording) and that nothing
 * errors in another language. Needs the German language pack:
 *
 *   pip install jupyterlab-language-pack-de-DE
 *
 * and skips without it.
 */
const SERVER = 'http://localhost:8888';
const LOCALE = 'de_DE';

type Catalog = Record<string, string[]>;

// Galata serves the page its own copy of the settings, so the language is
// set there; the server's (and the developer's) settings are never touched.
test.use({
  mockSettings: {
    ...galata.DEFAULT_SETTINGS,
    '@jupyterlab/translation-extension:plugin': { locale: LOCALE }
  },
  // Galata's own readiness check finds JupyterLab's controls by their
  // English names ("Simple", "Launcher"), which a German UI does not have.
  // Playwright requires a destructuring pattern for a fixture's first
  // argument, even an empty one.
  // eslint-disable-next-line no-empty-pattern
  waitForApplication: async ({}, use) => {
    await use(async page => {
      await page.locator('#jupyterlab-splash').waitFor({ state: 'detached' });
      await page.locator('.jp-LauncherCard').first().waitFor();
    });
  }
});

/** NBI's catalog as JupyterLab serves it for the locale, or null. */
async function nbiCatalog(
  request: APIRequestContext,
  locale: string
): Promise<Catalog | null> {
  const response = await request.get(
    `${SERVER}/lab/api/translations/${locale}`
  );
  if (!response.ok()) {
    return null;
  }
  const body = await response.json();
  return body?.data?.notebook_intelligence ?? null;
}

function translation(catalog: Catalog, msgid: string, context?: string) {
  const key = context ? `${context}\u0004${msgid}` : msgid;
  const value = catalog[key]?.[0];
  expect(value, `de_DE has no translation for ${key}`).toBeTruthy();
  return value as string;
}

test.describe('NBI in another language', () => {
  let catalog: Catalog | null = null;

  test.beforeAll(async ({ request }) => {
    const languages = await (
      await request.get(`${SERVER}/lab/api/translations/`)
    ).json();
    test.skip(
      !languages?.data?.[LOCALE],
      'Install jupyterlab-language-pack-de-DE to run this test.'
    );
    catalog = await nbiCatalog(request, LOCALE);
  });

  test('walks the main surfaces in German without errors', async ({
    page,
    request
  }) => {
    expect(catalog, 'NBI ships no de_DE catalog').toBeTruthy();
    const de = catalog as Catalog;
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      // The Performance tab asks for the last turn report, which is a 404
      // while diagnostics are off; the panel handles it.
      if (message.type() === 'error' && !message.text().includes('404')) {
        errors.push(message.text());
      }
    });

    // Chat sidebar.
    await openChatSidebar(page);
    // The header renders whether or not a chat provider is set up (a fresh
    // Galata workspace has none, so the prompt itself is hidden).
    await expect(
      page.getByRole('button', {
        name: translation(de, 'Open Notebook Intelligence settings')
      })
    ).toBeVisible();

    // Command palette label.
    const label = await page.evaluate(() =>
      (window as any).jupyterapp.commands.label(
        'notebook-intelligence:open-configuration-dialog'
      )
    );
    expect(label).toBe(translation(de, 'Notebook Intelligence Settings'));

    // Settings dialog: every tab opens.
    await page.evaluate(() =>
      (window as any).jupyterapp.commands.execute(
        'notebook-intelligence:open-configuration-dialog'
      )
    );
    const tabs = page.locator('.nbi-settings-panel-tab');
    await expect(tabs.first()).toBeVisible();
    await expect(
      page.locator('.model-config-section-header', {
        hasText: translation(de, 'Language', 'settings section')
      })
    ).toBeVisible();
    for (let i = 0; i < (await tabs.count()); i++) {
      await tabs.nth(i).click();
      await page.waitForTimeout(300);
    }

    // Server-written text follows the language too.
    const readiness = await request.get(
      `${SERVER}/notebook-intelligence/readiness?nbi_locale=${LOCALE}`
    );
    const report = await readiness.json();
    expect(report.checks[0].title).toBe(
      translation(de, 'Active chat path', 'readiness check')
    );

    expect(errors).toEqual([]);
  });
});
