// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, {
  ChangeEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState
} from 'react';
import { VscClose, VscSend, VscSparkle } from '../icons';

import { CheckBoxItem } from './checkbox';
import { useTrans } from '../i18n';

export interface INotebookGenerationPopoverProps {
  initialShowInChat?: boolean;
  onSubmit: (prompt: string, showInChat: boolean) => void;
  onClose: () => void;
}

export function NotebookGenerationPopover(
  props: INotebookGenerationPopoverProps
): JSX.Element {
  const trans = useTrans();
  const [prompt, setPrompt] = useState('');
  const [showInChat, setShowInChat] = useState<boolean>(
    props.initialShowInChat ?? true
  );
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Defer to the next frame so the focus call lands after Lumino's
    // attach lifecycle and JupyterLab's focus tracker have settled —
    // otherwise the active notebook can win the focus race and the
    // textarea stays unfocused (issue #231).
    const handle = window.requestAnimationFrame(() => {
      textareaRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(handle);
  }, []);

  const trimmed = prompt.trim();
  const canSubmit = trimmed.length > 0;

  const handleSubmit = () => {
    if (!canSubmit) {
      return;
    }
    props.onSubmit(trimmed, showInChat);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      event.preventDefault();
      props.onClose();
      return;
    }
  };

  const handleTextareaKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className="notebook-generation-popover"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
    >
      <div className="notebook-generation-popover-header">
        <div className="notebook-generation-popover-header-icon">
          <VscSparkle />
        </div>
        <div className="notebook-generation-popover-title">
          {trans.__('Update active notebook')}
        </div>
        <div style={{ flexGrow: 1 }}></div>
        <button
          type="button"
          className="notebook-generation-popover-close-button"
          aria-label={trans.__('Close notebook generation popover')}
          title={trans.__('Close')}
          onClick={props.onClose}
        >
          <VscClose aria-hidden="true" />
        </button>
      </div>
      <div className="notebook-generation-popover-body">
        <textarea
          ref={textareaRef}
          className="notebook-generation-popover-input"
          rows={4}
          placeholder={trans.__(
            'Describe how to update the active notebook...'
          )}
          value={prompt}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
            setPrompt(event.target.value)
          }
          onKeyDown={handleTextareaKeyDown}
        />
        <CheckBoxItem
          checked={showInChat}
          label={trans.__('Show in chat')}
          tooltip={trans.__(
            'When enabled, the prompt opens the Notebook Intelligence chat sidebar. Disable to keep the chat hidden and only show progress on the notebook toolbar.'
          )}
          onClick={() => setShowInChat(value => !value)}
        />
        <div className="notebook-generation-popover-actions">
          <button
            type="button"
            className="notebook-generation-popover-submit"
            disabled={!canSubmit}
            onClick={handleSubmit}
            title={trans.__('Generate (Enter)')}
          >
            <VscSend />
            <span>{trans.__('Generate')}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
