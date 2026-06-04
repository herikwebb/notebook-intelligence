import React from 'react';
import { render, screen } from '@testing-library/react';
import { ToolCallCard } from '../../src/components/tool-call-card';

describe('ToolCallCard', () => {
  it('renders the title and an in-progress status', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't1',
          title: 'Reading file',
          kind: 'read',
          status: 'in_progress'
        }}
      />
    );
    expect(screen.getByText('Reading file')).toBeInTheDocument();
    expect(container.querySelector('.nbi-tool-call')).toHaveClass(
      'nbi-tool-call-in-progress'
    );
    // Status reaches screen readers as text (icons are decorative).
    expect(screen.getByText('in progress')).toBeInTheDocument();
  });

  it('renders a completed status', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't2',
          title: 'Editing cell',
          kind: 'edit',
          status: 'completed'
        }}
      />
    );
    expect(container.querySelector('.nbi-tool-call')).toHaveClass(
      'nbi-tool-call-completed'
    );
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('renders a failed status', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't3',
          title: 'Running shell command',
          kind: 'execute',
          status: 'failed'
        }}
      />
    );
    expect(container.querySelector('.nbi-tool-call')).toHaveClass(
      'nbi-tool-call-failed'
    );
    expect(screen.getByText('failed')).toBeInTheDocument();
  });

  it('falls back gracefully for an unknown kind and status', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't4',
          title: 'Mystery',
          kind: 'weird',
          status: 'queued'
        }}
      />
    );
    expect(screen.getByText('Mystery')).toBeInTheDocument();
    // Unknown status is kept verbatim (kebabbed) as the modifier + sr label.
    expect(container.querySelector('.nbi-tool-call')).toHaveClass(
      'nbi-tool-call-queued'
    );
    expect(screen.getByText('queued')).toBeInTheDocument();
  });

  it('renders a cancelled status', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't6',
          title: 'Running shell command',
          kind: 'execute',
          status: 'cancelled'
        }}
      />
    );
    expect(container.querySelector('.nbi-tool-call')).toHaveClass(
      'nbi-tool-call-cancelled'
    );
    expect(screen.getByText('cancelled')).toBeInTheDocument();
  });

  it('renders a leading kind icon and a status icon, both decorative', () => {
    const { container } = render(
      <ToolCallCard
        toolCall={{
          id: 't5',
          title: 'Reading',
          kind: 'read',
          status: 'completed'
        }}
      />
    );
    const kindIcon = container.querySelector('.nbi-tool-call-kind-icon');
    const statusIcon = container.querySelector('.nbi-tool-call-status-icon');
    expect(kindIcon).toBeTruthy();
    expect(statusIcon).toBeTruthy();
    // Icons are decorative; status reaches screen readers via the sr-only text.
    expect(kindIcon).toHaveAttribute('aria-hidden', 'true');
    expect(statusIcon).toHaveAttribute('aria-hidden', 'true');
  });
});
