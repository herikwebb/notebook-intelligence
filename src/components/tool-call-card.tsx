import React from 'react';
import {
  VscClose,
  VscEdit,
  VscError,
  VscEye,
  VscPassFilled,
  VscSync,
  VscTerminal,
  VscTools
} from '../icons';

/**
 * A single agent tool call surfaced as a persistent chat card. Mirrors the
 * `ToolCallData` payload emitted by the server: it stays in the transcript
 * after the turn ends and carries its final status, unlike the transient
 * single progress line it replaces.
 */
export interface IToolCall {
  id: string;
  title: string;
  // Coarse category, used only to pick the leading icon.
  kind: 'read' | 'edit' | 'execute' | 'other' | string;
  status: 'in_progress' | 'completed' | 'failed' | 'cancelled' | string;
}

const KIND_ICONS: Record<string, React.FC<any>> = {
  read: VscEye,
  edit: VscEdit,
  execute: VscTerminal,
  other: VscTools
};

const STATUS_LABELS: Record<string, string> = {
  in_progress: 'in progress',
  completed: 'completed',
  failed: 'failed',
  cancelled: 'cancelled'
};

export function ToolCallCard(props: { toolCall: IToolCall }): JSX.Element {
  const { title, kind, status } = props.toolCall;
  const KindIcon = KIND_ICONS[kind] ?? VscTools;

  let StatusIcon = VscSync;
  if (status === 'completed') {
    StatusIcon = VscPassFilled;
  } else if (status === 'failed') {
    StatusIcon = VscError;
  } else if (status === 'cancelled') {
    StatusIcon = VscClose;
  }

  const statusLabel = STATUS_LABELS[status] ?? status;
  const statusModifier = status.replace(/_/g, '-');

  return (
    <div className={`nbi-tool-call nbi-tool-call-${statusModifier}`}>
      <KindIcon className="nbi-tool-call-kind-icon" aria-hidden="true" />
      <span className="nbi-tool-call-title" title={title}>
        {title}
      </span>
      <StatusIcon className="nbi-tool-call-status-icon" aria-hidden="true" />
      {/* Status reaches screen readers as text; the icons are decorative.
          The visible title is already in the accessibility tree, so this
          span carries only the status to avoid announcing the title twice. */}
      <span className="nbi-sr-only">{statusLabel}</span>
    </div>
  );
}
