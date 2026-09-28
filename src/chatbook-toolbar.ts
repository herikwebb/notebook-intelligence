// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { JupyterFrontEnd } from '@jupyterlab/application';
import { Dialog, showDialog } from '@jupyterlab/apputils';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import { INotebookModel, NotebookPanel } from '@jupyterlab/notebook';
import { LabIcon, ToolbarButton } from '@jupyterlab/ui-components';
import { IDisposable, DisposableDelegate } from '@lumino/disposable';

import {
  convertNotebookToChatbook,
  exportChatbookNotebookAsCode,
  isChatbookSession,
  nextChatbookNotebookMode,
  toggleAllChatbookCellModes
} from './chatbook';
import {
  chatbookConversionFit,
  chatbookLanguageId,
  chatbookSourceKernel,
  isChatbookKernelName
} from './chatbook-core';
import { NBIAPI } from './api';
import { CommandIDs } from './command-ids';
import {
  NotebookKernelNotFoundError,
  findKernelProfile,
  listChatbookBackendProfiles,
  resolveChatbookBackendProfile,
  sharedKernelSpecManager
} from './notebook-kernels';
import switchSvgstr from '../style/icons/chatbook-switch.svg';
import exportSvgstr from '../style/icons/chatbook-export.svg';
import convertSvgstr from '../style/icons/chatbook-convert.svg';

const SHOW_CODE_BUTTON_NAME = 'nbi-chatbook-show-code';
const CONVERT_BUTTON_NAME = 'nbi-chatbook-convert';
const TO_CHATBOOK_BUTTON_NAME = 'nbi-convert-to-chatbook';

const switchIcon = new LabIcon({
  name: 'notebook-intelligence:chatbook-switch',
  svgstr: switchSvgstr
});
const exportIcon = new LabIcon({
  name: 'notebook-intelligence:chatbook-export',
  svgstr: exportSvgstr
});
export const convertToChatbookIcon = new LabIcon({
  name: 'notebook-intelligence:chatbook-convert',
  svgstr: convertSvgstr
});

/** Whether a notebook panel is a candidate for Convert to Chatbook. */
export function canConvertToChatbook(panel: NotebookPanel): boolean {
  if (
    !NBIAPI.config.chatbookEnabled ||
    !panel.model ||
    !panel.context.isReady ||
    isChatbookSession(panel.sessionContext)
  ) {
    return false;
  }
  // A Chatbook opened with No Kernel is still a Chatbook.
  const kernel = chatbookSourceKernel({
    kernelspec: panel.model.getMetadata('kernelspec')
  });
  return !isChatbookKernelName(kernel.name);
}

/** A language id as people write it: `r` is R, `python` is Python. */
function languageLabel(language: string): string {
  const known: Record<string, string> = {
    python: 'Python',
    r: 'R',
    julia: 'Julia',
    javascript: 'JavaScript',
    typescript: 'TypeScript',
    sql: 'SQL'
  };
  return (
    known[language] ?? language.charAt(0).toUpperCase() + language.slice(1)
  );
}

let converting = false;

/**
 * Ask, then write a Chatbook copy of `panel` next to it and open it. Blocks
 * when the notebook's language differs from the Chatbook execution kernel,
 * which is one setting shared by every Chatbook, rather than changing it.
 */
export async function confirmConvertToChatbook(
  app: JupyterFrontEnd,
  panel: NotebookPanel
): Promise<void> {
  if (converting || !canConvertToChatbook(panel)) {
    return;
  }
  converting = true;
  try {
    await runConvertToChatbook(app, panel);
  } finally {
    converting = false;
  }
}

async function runConvertToChatbook(
  app: JupyterFrontEnd,
  panel: NotebookPanel
): Promise<void> {
  const kernels = sharedKernelSpecManager();
  await kernels.ready;
  const specs = kernels.specs?.kernelspecs;
  const backend = resolveChatbookBackendProfile(
    specs,
    NBIAPI.config.chatbookBackendKernel
  );
  const source = chatbookSourceKernel(panel.model!.metadata);
  const fit = chatbookConversionFit(source, backend);

  if (fit === 'different-language') {
    const language = languageLabel(source.language);
    const installed = listChatbookBackendProfiles(specs).some(
      profile => chatbookLanguageId(profile.language) === source.language
    );
    const result = await showDialog({
      title: "Can't convert this notebook yet",
      body:
        `This notebook is written in ${language}, but Chatbook runs all ` +
        `code in ${backend.displayName}, so its code cells would fail. ` +
        (installed
          ? 'To convert it, set Settings > Chatbook > Execution kernel to ' +
            `a kernel for ${language}, then convert again. That setting applies ` +
            'to every Chatbook, so your existing Chatbooks would run ' +
            `${language} too.`
          : `No ${language} kernel is installed for Chatbook to use. ` +
            'Install one, then choose it in Settings > Chatbook > ' +
            'Execution kernel.'),
      buttons: installed
        ? [
            Dialog.cancelButton(),
            Dialog.okButton({ label: 'Open Chatbook settings' })
          ]
        : [Dialog.cancelButton({ label: 'Close' })]
    });
    if (installed && result.button.accept) {
      void app.commands.execute(CommandIDs.openConfigurationDialog, {
        tab: 'chatbook'
      });
    }
    return;
  }

  let kernelNote = '';
  const from =
    source.displayName && source.displayName !== backend.displayName
      ? source.displayName
      : source.name;
  if (fit === 'same-language' && from) {
    kernelNote = ` Its code will run in ${backend.displayName}, the Chatbook execution kernel, instead of ${from}.`;
  } else if (fit !== 'same-kernel') {
    kernelNote = ` Its code will run in ${backend.displayName}, the Chatbook execution kernel.`;
  }
  const result = await showDialog({
    title: 'Convert to Chatbook',
    body:
      'Creates a Chatbook copy of this notebook next to it and opens it, ' +
      'including any unsaved changes. Code cells become Chatbook code cells ' +
      'and run exactly as written; outputs and markdown are kept. The ' +
      `original is not changed.${kernelNote} Nothing is sent to the model ` +
      'now. The first time each code cell runs successfully, its code is ' +
      'sent to the model for a one-line English description.',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Convert' })]
  });
  if (!result.button.accept) {
    return;
  }

  let path: string;
  try {
    path = await convertNotebookToChatbook(panel, app.serviceManager.contents);
  } catch (error) {
    void app.commands.execute('apputils:notify', {
      message: `Could not convert to Chatbook: ${error instanceof Error ? error.message : error}`,
      type: 'error',
      options: { autoClose: true }
    });
    return;
  }
  void app.commands.execute('apputils:notify', {
    message: `Created Chatbook copy: ${path}`,
    type: 'success',
    options: { autoClose: true }
  });
  try {
    await app.commands.execute('docmanager:open', { path });
  } catch (error) {
    console.error(`Could not open ${path}`, error);
  }
}

export async function confirmConvertChatbookNotebook(
  app: JupyterFrontEnd,
  panel: NotebookPanel
): Promise<void> {
  if (!isChatbookSession(panel.sessionContext)) {
    return;
  }
  const kernels = sharedKernelSpecManager();
  await kernels.ready;
  const profile = resolveChatbookBackendProfile(
    kernels.specs?.kernelspecs,
    NBIAPI.config.chatbookBackendKernel
  );
  const result = await showDialog({
    title: `Export as ${profile.language} notebook`,
    body: `Create a new ${profile.displayName} notebook from this Chatbook. The original Chatbook is left unchanged. Cells that have not been run become comments.`,
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Export' })]
  });
  if (!result.button.accept) {
    return;
  }

  let resolved = profile;
  try {
    resolved = findKernelProfile(kernels.specs?.kernelspecs, {
      kernelName: profile.kernelName
    });
  } catch (error) {
    if (error instanceof NotebookKernelNotFoundError) {
      void app.commands.execute('apputils:notify', {
        message: error.message,
        type: 'error',
        options: { autoClose: true }
      });
      return;
    }
    throw error;
  }

  let path: string;
  try {
    path = await exportChatbookNotebookAsCode(
      panel,
      resolved,
      app.serviceManager.contents
    );
  } catch (error) {
    void app.commands.execute('apputils:notify', {
      message: `Export failed: ${error instanceof Error ? error.message : error}`,
      type: 'error',
      options: { autoClose: true }
    });
    return;
  }
  await app.commands.execute('docmanager:open', { path });
  void app.commands.execute('apputils:notify', {
    message: `Exported ${path}`,
    type: 'success',
    options: { autoClose: true }
  });
}

class ChatbookToolbarController {
  constructor(app: JupyterFrontEnd, panel: NotebookPanel) {
    this._app = app;
    this._panel = panel;
    this._showCodeButton = new ToolbarButton({
      icon: switchIcon,
      tooltip: 'Switch every cell to code',
      onClick: () => {
        toggleAllChatbookCellModes(this._panel);
        this.sync();
      }
    });
    this._showCodeButton.addClass('nbi-chatbook-toolbar-button');
    this._convertButton = new ToolbarButton({
      icon: exportIcon,
      tooltip: 'Export as a notebook for the Chatbook backend kernel',
      onClick: () => {
        void confirmConvertChatbookNotebook(this._app, this._panel);
      }
    });
    this._convertButton.addClass('nbi-chatbook-toolbar-button');
    this._toChatbookButton = new ToolbarButton({
      icon: convertToChatbookIcon,
      tooltip: 'Convert to Chatbook',
      onClick: () => {
        void confirmConvertToChatbook(this._app, this._panel);
      }
    });
    this._toChatbookButton.addClass('nbi-chatbook-toolbar-button');
    this._showCodeButton.hide();
    this._convertButton.hide();
    this._toChatbookButton.hide();
    panel.toolbar.insertAfter(
      'cellType',
      SHOW_CODE_BUTTON_NAME,
      this._showCodeButton
    );
    panel.toolbar.insertAfter(
      SHOW_CODE_BUTTON_NAME,
      CONVERT_BUTTON_NAME,
      this._convertButton
    );
    panel.toolbar.insertAfter(
      CONVERT_BUTTON_NAME,
      TO_CHATBOOK_BUTTON_NAME,
      this._toChatbookButton
    );
    panel.sessionContext.kernelChanged.connect(this.sync, this);
    panel.sessionContext.sessionChanged.connect(this.sync, this);
    void panel.sessionContext.ready.then(() => this.sync());
    // The kernelspec metadata changes after the kernel does, and a model is
    // empty until the file loads; both decide the Convert button.
    panel.model?.metadataChanged.connect(this._scheduleSync);
    NBIAPI.configChanged.connect(this._scheduleSync);
    panel.context.ready
      .then(() => {
        if (!this._disposed) {
          this.sync();
        }
      })
      .catch(() => undefined);
    this.sync();
  }

  sync(): void {
    const isChatbook = isChatbookSession(this._panel.sessionContext);
    if (isChatbook && !this._contentChangedConnected) {
      this._panel.model?.contentChanged.connect(this._scheduleSync);
      this._contentChangedConnected = true;
    } else if (!isChatbook && this._contentChangedConnected) {
      this._panel.model?.contentChanged.disconnect(this._scheduleSync);
      this._contentChangedConnected = false;
    }
    if (isChatbook) {
      this._showCodeButton.show();
      this._convertButton.show();
    } else {
      this._showCodeButton.hide();
      this._convertButton.hide();
    }
    if (canConvertToChatbook(this._panel)) {
      this._toChatbookButton.show();
    } else {
      this._toChatbookButton.hide();
    }
    const allPython = nextChatbookNotebookMode(this._panel) === 'prompt';
    this._showCodeButton.pressed = allPython;
    this._showCodeButton.node.title = allPython
      ? 'Switch every cell to natural language'
      : 'Switch every cell to code';
  }

  dispose(): void {
    this._panel.sessionContext.kernelChanged.disconnect(this.sync, this);
    this._panel.sessionContext.sessionChanged.disconnect(this.sync, this);
    this._disposed = true;
    this._panel.model?.metadataChanged.disconnect(this._scheduleSync);
    NBIAPI.configChanged.disconnect(this._scheduleSync);
    if (this._contentChangedConnected) {
      this._panel.model?.contentChanged.disconnect(this._scheduleSync);
      this._contentChangedConnected = false;
    }
    if (this._syncFrame) {
      cancelAnimationFrame(this._syncFrame);
      this._syncFrame = 0;
    }
    this._showCodeButton.dispose();
    this._convertButton.dispose();
    this._toChatbookButton.dispose();
  }

  private _app: JupyterFrontEnd;
  private _panel: NotebookPanel;
  private _showCodeButton: ToolbarButton;
  private _convertButton: ToolbarButton;
  private _toChatbookButton: ToolbarButton;
  private _contentChangedConnected = false;
  private _disposed = false;
  private _syncFrame = 0;
  private _scheduleSync = (): void => {
    if (this._syncFrame) {
      return;
    }
    this._syncFrame = requestAnimationFrame(() => {
      this._syncFrame = 0;
      this.sync();
    });
  };
}

export class ChatbookToolbarExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel>
{
  constructor(app: JupyterFrontEnd) {
    this._app = app;
  }

  createNew(
    panel: NotebookPanel,
    _context: DocumentRegistry.IContext<INotebookModel>
  ): IDisposable {
    const controller = new ChatbookToolbarController(this._app, panel);
    return new DisposableDelegate(() => {
      controller.dispose();
    });
  }

  private _app: JupyterFrontEnd;
}
