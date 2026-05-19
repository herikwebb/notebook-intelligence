// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

jest.mock('@jupyterlab/apputils', () => ({
  Dialog: {
    cancelButton: jest.fn(() => ({})),
    warnButton: jest.fn(() => ({ accept: true }))
  },
  showDialog: jest.fn(() => Promise.resolve({ button: { accept: true } }))
}));

jest.mock('../../src/api', () => ({
  NBIAPI: {
    config: {
      allowGithubPluginImport: true
    },
    configChanged: {
      connect: jest.fn(),
      disconnect: jest.fn()
    },
    listPlugins: jest.fn(),
    listPluginMarketplaces: jest.fn(),
    listPluginMarketplacePlugins: jest.fn(),
    installPlugin: jest.fn(),
    removePluginMarketplace: jest.fn(),
    updatePluginMarketplace: jest.fn()
  }
}));

import { NBIAPI } from '../../src/api';
import {
  SettingsPanelComponentPlugins,
  summarizePluginNames
} from '../../src/components/plugins-panel';

describe('SettingsPanelComponentPlugins', () => {
  const api = NBIAPI as any;

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = '';
    api.listPlugins.mockResolvedValue([]);
    api.listPluginMarketplaces.mockResolvedValue([
      { name: 'official', source: 'github:anthropics/claude-code' }
    ]);
    api.listPluginMarketplacePlugins.mockResolvedValue([
      { name: 'alpha', description: 'Alpha plugin' },
      { name: 'beta', description: 'Beta plugin' }
    ]);
    api.installPlugin.mockResolvedValue(undefined);
  });

  it('installs the selected plugin from the selected marketplace', async () => {
    render(<SettingsPanelComponentPlugins />);

    await screen.findByText('official');
    fireEvent.click(screen.getByRole('button', { name: 'Install plugin' }));

    await waitFor(() => {
      expect(api.listPluginMarketplacePlugins).toHaveBeenCalledWith('official');
    });

    const selects = Array.from(
      document.querySelectorAll('.nbi-modal-card select')
    ) as HTMLSelectElement[];
    expect(selects).toHaveLength(4);
    expect(selects[0].value).toBe('marketplace');
    expect(selects[1].value).toBe('official');
    expect(selects[2].value).toBe('alpha');

    fireEvent.change(selects[2], { target: { value: 'beta' } });
    fireEvent.click(screen.getByRole('button', { name: 'Install' }));

    await waitFor(() => {
      expect(api.installPlugin).toHaveBeenCalledWith('beta@official', 'user');
    });
  });

  it('allows a plugin reference to be specified manually', async () => {
    render(<SettingsPanelComponentPlugins />);

    await screen.findByText('official');
    fireEvent.click(screen.getByRole('button', { name: 'Install plugin' }));

    const selects = Array.from(
      document.querySelectorAll('.nbi-modal-card select')
    ) as HTMLSelectElement[];
    fireEvent.change(selects[0], { target: { value: 'manual' } });

    const input = document.querySelector(
      '.nbi-modal-card input[type="text"]'
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '  gamma@official  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Install' }));

    await waitFor(() => {
      expect(api.installPlugin).toHaveBeenCalledWith('gamma@official', 'user');
    });
  });

  it('keeps manual install available when no marketplace cache is configured', async () => {
    api.listPluginMarketplaces.mockResolvedValue([]);

    render(<SettingsPanelComponentPlugins />);

    await screen.findByText(
      'No marketplaces configured. Add one to discover plugins.'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Install plugin' }));

    const input = document.querySelector(
      '.nbi-modal-card input[type="text"]'
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'manual-plugin@official' } });
    fireEvent.click(screen.getByRole('button', { name: 'Install' }));

    await waitFor(() => {
      expect(api.installPlugin).toHaveBeenCalledWith(
        'manual-plugin@official',
        'user'
      );
    });
    expect(api.listPluginMarketplacePlugins).not.toHaveBeenCalled();
  });

  it('uses marketplace plugin id when name is absent', async () => {
    api.listPluginMarketplacePlugins.mockResolvedValue([
      { id: 'id-only', description: 'ID-only plugin' }
    ]);

    render(<SettingsPanelComponentPlugins />);

    await screen.findByText('official');
    fireEvent.click(screen.getByRole('button', { name: 'Install plugin' }));

    await waitFor(() => {
      expect(api.listPluginMarketplacePlugins).toHaveBeenCalledWith('official');
    });

    const selects = Array.from(
      document.querySelectorAll('.nbi-modal-card select')
    ) as HTMLSelectElement[];
    expect(selects[2].value).toBe('id-only');
    fireEvent.click(screen.getByRole('button', { name: 'Install' }));

    await waitFor(() => {
      expect(api.installPlugin).toHaveBeenCalledWith(
        'id-only@official',
        'user'
      );
    });
  });

  describe('marketplace row', () => {
    beforeEach(() => {
      api.listPluginMarketplaces.mockResolvedValue([
        {
          name: 'acme',
          source: 'github:acme/marketplace',
          description: 'Acme team plugins',
          version: '1.2.3',
          plugin_count: 2,
          plugin_names: ['alpha', 'beta']
        }
      ]);
      api.updatePluginMarketplace.mockResolvedValue(undefined);
    });

    it('renders description, version, and plugin summary', async () => {
      render(<SettingsPanelComponentPlugins />);

      await screen.findByText('acme');
      expect(screen.getByText('Acme team plugins')).toBeInTheDocument();
      expect(screen.getByText('v1.2.3')).toBeInTheDocument();
      // The plugin summary lands inside a div together with the count
      // label, so search by class to pick up both halves.
      const pluginSummary = document.querySelector(
        '.nbi-skill-row-plugins'
      ) as HTMLElement;
      expect(pluginSummary.textContent).toContain('2 plugins');
      expect(pluginSummary.textContent).toContain('alpha, beta');
    });

    it('trims long plugin lists with a +N more tail', async () => {
      api.listPluginMarketplaces.mockResolvedValue([
        {
          name: 'big',
          source: './big',
          plugin_count: 9,
          plugin_names: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        }
      ]);

      render(<SettingsPanelComponentPlugins />);
      await screen.findByText('big');
      const pluginSummary = document.querySelector(
        '.nbi-skill-row-plugins'
      ) as HTMLElement;
      expect(pluginSummary.textContent).toContain('9 plugins');
      expect(pluginSummary.textContent).toContain('a, b, c, d, e, +4 more');
    });

    it('renders "no plugins" when the count is zero', async () => {
      api.listPluginMarketplaces.mockResolvedValue([
        { name: 'empty', source: './empty', plugin_count: 0, plugin_names: [] }
      ]);
      render(<SettingsPanelComponentPlugins />);
      await screen.findByText('empty');
      const pluginSummary = document.querySelector(
        '.nbi-skill-row-plugins'
      ) as HTMLElement;
      expect(pluginSummary.textContent).toBe('no plugins');
    });

    it('omits the plugin line entirely when manifest data is absent', async () => {
      // Manifest read failed or just-added marketplace not yet cached:
      // the backend omits plugin_count + plugin_names. The row must
      // not render a misleading "no plugins" line in that case.
      api.listPluginMarketplaces.mockResolvedValue([
        { name: 'pending', source: './pending' }
      ]);
      render(<SettingsPanelComponentPlugins />);
      await screen.findByText('pending');
      expect(document.querySelector('.nbi-skill-row-plugins')).toBeNull();
    });

    it('calls updatePluginMarketplace on click', async () => {
      render(<SettingsPanelComponentPlugins />);

      await screen.findByText('acme');
      fireEvent.click(screen.getByRole('button', { name: 'Update' }));

      await waitFor(() => {
        expect(api.updatePluginMarketplace).toHaveBeenCalledWith('acme');
      });
      // After a successful update the panel refreshes its data.
      expect(api.listPluginMarketplaces.mock.calls.length).toBeGreaterThan(1);
    });

    it('shows Updating… and disables both row buttons while in flight', async () => {
      // Hold the update call open with a deferred promise so the test
      // can observe the busy state. Without this, the resolve happens
      // before the assertions and the disabled flip is invisible.
      let resolveUpdate: () => void = () => undefined;
      api.updatePluginMarketplace.mockImplementationOnce(
        () =>
          new Promise<void>(resolve => {
            resolveUpdate = resolve;
          })
      );
      render(<SettingsPanelComponentPlugins />);
      await screen.findByText('acme');
      fireEvent.click(screen.getByRole('button', { name: 'Update' }));
      const updating = await screen.findByRole('button', {
        name: 'Updating…'
      });
      expect(updating).toBeDisabled();
      // When the row is busy, Remove's label also flips to "Removing…"
      // so both buttons disable in tandem. The label flip itself is
      // worth pinning: a regression that kept the Remove label static
      // would also pass `disabled`, but the user wouldn't see why both
      // buttons are inert.
      expect(screen.getByRole('button', { name: 'Removing…' })).toBeDisabled();
      resolveUpdate();
      await waitFor(() => {
        expect(api.updatePluginMarketplace).toHaveBeenCalled();
      });
    });

    it('shows an error when the update fails', async () => {
      api.updatePluginMarketplace.mockRejectedValueOnce(
        new Error('network down')
      );
      render(<SettingsPanelComponentPlugins />);
      await screen.findByText('acme');
      fireEvent.click(screen.getByRole('button', { name: 'Update' }));
      await screen.findByText(/Failed to update marketplace: network down/);
    });
  });
});

describe('summarizePluginNames', () => {
  it('returns empty string for undefined / empty', () => {
    expect(summarizePluginNames(undefined, 5)).toBe('');
    expect(summarizePluginNames([], 5)).toBe('');
  });

  it('returns the full list when under the visible cap', () => {
    expect(summarizePluginNames(['a', 'b'], 5)).toBe('a, b');
  });

  it('returns the full list when exactly at the visible cap', () => {
    expect(summarizePluginNames(['a', 'b', 'c'], 3)).toBe('a, b, c');
  });

  it('truncates and appends +N more when over the cap', () => {
    expect(summarizePluginNames(['a', 'b', 'c', 'd', 'e'], 3)).toBe(
      'a, b, c, +2 more'
    );
  });
});
