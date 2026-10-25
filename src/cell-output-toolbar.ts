// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { JupyterFrontEnd } from '@jupyterlab/application';
import { CodeCell } from '@jupyterlab/cells';
import { NotebookPanel } from '@jupyterlab/notebook';
import { LabIcon } from '@jupyterlab/ui-components';
import { CommandRegistry } from '@lumino/commands';
import { IDisposable } from '@lumino/disposable';
import { CellOutputActionFlag, NBIAPI } from './api';
import { cellOutputHasError } from './utils';
import { TranslationBundle } from '@jupyterlab/translation';
import { getTrans } from './i18n';
import sparkleSvgstr from '../style/icons/cell-toolbar-sparkle.svg';
import chatSvgstr from '../style/icons/cell-toolbar-chat.svg';
import bugSvgstr from '../style/icons/cell-toolbar-bug.svg';

interface IToolbarAction {
  id: string;
  label: string;
  title: string;
  icon: LabIcon;
  command: string;
  /** Hide the button when this feature flag is disabled. */
  featureFlag: CellOutputActionFlag;
  /** Only show when the cell has at least one error output. */
  requireError?: boolean;
}

const TOOLBAR_CLASS = 'nbi-cell-output-toolbar';
const BUTTON_CLASS = 'nbi-cell-output-toolbar-button';

// SVGs live under style/icons/ and are loaded via LabIcon to match the rest
// of the project's icon plumbing. The source assets are Microsoft's
// vscode-codicons (sparkle, comment-discussion, bug), CC BY 4.0 — the
// license header lives inside each .svg file.
const sparkleIcon = new LabIcon({
  name: 'notebook-intelligence:cell-toolbar-sparkle',
  svgstr: sparkleSvgstr
});
const chatIcon = new LabIcon({
  name: 'notebook-intelligence:cell-toolbar-chat',
  svgstr: chatSvgstr
});
const bugIcon = new LabIcon({
  name: 'notebook-intelligence:cell-toolbar-bug',
  svgstr: bugSvgstr
});

// A function so the labels are translated when the toolbar is built, not
// when this module loads.
const actions = (trans: TranslationBundle): IToolbarAction[] => [
  {
    id: 'explain',
    label: trans._p('cell output toolbar', 'Explain'),
    title: trans.__("Explain this cell's output"),
    icon: sparkleIcon,
    command: 'notebook-intelligence:editor-explain-this-output',
    featureFlag: 'output_followup'
  },
  {
    id: 'ask',
    label: trans._p('cell output toolbar', 'Ask'),
    title: trans.__('Ask about this output'),
    icon: chatIcon,
    command: 'notebook-intelligence:editor-ask-about-this-output',
    featureFlag: 'output_followup'
  },
  {
    id: 'troubleshoot',
    label: trans._p('cell output toolbar', 'Troubleshoot'),
    title: trans.__('Troubleshoot the error in this cell'),
    icon: bugIcon,
    command: 'notebook-intelligence:editor-troubleshoot-this-output',
    featureFlag: 'explain_error',
    requireError: true
  }
];

/**
 * Show a hover toolbar over Jupyter cell outputs that surfaces the existing
 * Explain / Ask / Troubleshoot commands as one-click buttons.
 *
 * The toolbar respects the `output_toolbar` feature flag (whole-toolbar
 * gate) and the per-action `explain_error` / `output_followup` flags so a
 * locked-off feature stays locked off here too.
 */
export class CellOutputHoverToolbar implements IDisposable {
  private _app: JupyterFrontEnd;
  private _commands: CommandRegistry;
  private _disposed = false;
  private _activeArea: HTMLElement | null = null;
  private _onMouseOver: (event: MouseEvent) => void;
  private _onMouseLeave: () => void;

  constructor(app: JupyterFrontEnd, commands: CommandRegistry) {
    this._app = app;
    // The Explain / Ask / Troubleshoot commands live on the context-menu's
    // private CommandRegistry, not on `app.commands`, so callers must pass
    // the same registry the menu uses.
    this._commands = commands;
    this._onMouseOver = this._handleMouseOver.bind(this);
    // mouseleave only fires when the cursor exits the area entirely —
    // descendants (including the toolbar itself) don't trigger it.
    this._onMouseLeave = this._removeActiveToolbar.bind(this);
    document.body.addEventListener('mouseover', this._onMouseOver);
  }

  get isDisposed(): boolean {
    return this._disposed;
  }

  dispose(): void {
    if (this._disposed) {
      return;
    }
    this._disposed = true;
    document.body.removeEventListener('mouseover', this._onMouseOver);
    this._removeActiveToolbar();
  }

  private _handleMouseOver(event: MouseEvent): void {
    if (!NBIAPI.config.cellOutputFeatures.output_toolbar.enabled) {
      this._removeActiveToolbar();
      return;
    }
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }
    const area = target.closest<HTMLElement>('.jp-Cell-outputArea');
    if (!area) {
      return;
    }
    if (area === this._activeArea) {
      return;
    }
    this._removeActiveToolbar();
    const cellEl = area.closest<HTMLElement>('.jp-Cell');
    if (!cellEl) {
      return;
    }
    const located = this._locateCell(cellEl);
    if (!located) {
      return;
    }
    const toolbar = this._buildToolbar(
      located.panel,
      located.cellIndex,
      located.cell
    );
    if (!toolbar) {
      return;
    }
    area.appendChild(toolbar);
    this._activeArea = area;
    area.addEventListener('mouseleave', this._onMouseLeave);
  }

  private _removeActiveToolbar(): void {
    if (!this._activeArea) {
      return;
    }
    this._activeArea.removeEventListener('mouseleave', this._onMouseLeave);
    const existing = this._activeArea.querySelector(`.${TOOLBAR_CLASS}`);
    if (existing) {
      existing.remove();
    }
    this._activeArea = null;
  }

  private _locateCell(
    cellEl: HTMLElement
  ): { panel: NotebookPanel; cell: CodeCell; cellIndex: number } | null {
    const widget = this._app.shell.currentWidget;
    if (!(widget instanceof NotebookPanel)) {
      return null;
    }
    const widgets = widget.content.widgets;
    for (let i = 0; i < widgets.length; i++) {
      const cell = widgets[i];
      if (cell.node === cellEl && cell instanceof CodeCell) {
        return { panel: widget, cell, cellIndex: i };
      }
    }
    return null;
  }

  private _buildToolbar(
    panel: NotebookPanel,
    cellIndex: number,
    cell: CodeCell
  ): HTMLElement | null {
    const features = NBIAPI.config.cellOutputFeatures;
    const hasError = cellOutputHasError(cell);

    const trans = getTrans();
    const visible = actions(trans).filter(a => {
      if (!features[a.featureFlag].enabled) {
        return false;
      }
      if (a.requireError && !hasError) {
        return false;
      }
      return true;
    });
    if (visible.length === 0) {
      return null;
    }

    const toolbar = document.createElement('div');
    toolbar.className = TOOLBAR_CLASS;
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute(
      'aria-label',
      trans.__('Notebook Intelligence cell actions')
    );

    for (const action of visible) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = BUTTON_CLASS;
      button.title = action.title;
      button.setAttribute('aria-label', action.title);
      action.icon.element({ container: button, tag: 'span' });
      const label = document.createElement('span');
      label.className = `${BUTTON_CLASS}-label`;
      label.textContent = action.label;
      button.appendChild(label);
      button.addEventListener('click', event => {
        event.stopPropagation();
        // The editor commands act on the active cell, so activate the
        // hovered one first.
        panel.content.activeCellIndex = cellIndex;
        void this._commands.execute(action.command);
      });
      toolbar.appendChild(button);
    }
    return toolbar;
  }
}
