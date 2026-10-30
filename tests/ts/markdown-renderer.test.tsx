// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { MarkdownLink } from '../../src/components/markdown-link';

function fakeApp(execute: jest.Mock) {
  return {
    commands: { execute }
  } as any;
}

describe('MarkdownLink (issue #344)', () => {
  it('renders an http link via SafeAnchor with target=_blank', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir=""
        href="https://example.com/docs"
      >
        the docs
      </MarkdownLink>
    );
    const anchor = screen.getByRole('link', { name: /the docs/ });
    expect(anchor).toHaveAttribute('href', 'https://example.com/docs');
    expect(anchor).toHaveAttribute('target', '_blank');
    expect(anchor).toHaveAttribute('rel', 'noopener noreferrer');
    expect(execute).not.toHaveBeenCalled();
  });

  it('blocks javascript: hrefs', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir=""
        href="javascript:alert(1)"
      >
        click me
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(/link blocked/)).toHaveClass('nbi-sr-only');
  });

  it('routes workspace-relative paths through docmanager:open', () => {
    const execute = jest.fn().mockResolvedValue(undefined);
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href="README.md">
        the README
      </MarkdownLink>
    );
    const anchor = screen.getByRole('link', { name: /the README/ });
    expect(anchor).not.toHaveAttribute('target', '_blank');
    fireEvent.click(anchor);
    expect(execute).toHaveBeenCalledWith('docmanager:open', {
      path: 'README.md'
    });
  });

  it('resolves workspace-relative paths against baseDir and previews on hover', () => {
    const execute = jest.fn().mockResolvedValue(undefined);
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir="notebooks/proj"
        href="README.md"
      >
        the README
      </MarkdownLink>
    );
    const anchor = screen.getByRole('link', { name: /the README/ });
    // href is intentionally `#` so a modifier-click can't bypass the
    // onClick and let the browser navigate /lab/<path> in a new tab.
    // The resolved path is exposed via `title` for hover preview.
    expect(anchor).toHaveAttribute('href', '#');
    expect(anchor).toHaveAttribute('title', 'notebooks/proj/README.md');
    fireEvent.click(anchor);
    expect(execute).toHaveBeenCalledWith('docmanager:open', {
      path: 'notebooks/proj/README.md'
    });
  });

  it('resolves nested workspace-relative paths', () => {
    const execute = jest.fn().mockResolvedValue(undefined);
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir="notebooks/proj"
        href="data/intro.ipynb"
      >
        intro notebook
      </MarkdownLink>
    );
    fireEvent.click(screen.getByRole('link', { name: /intro notebook/ }));
    expect(execute).toHaveBeenCalledWith('docmanager:open', {
      path: 'notebooks/proj/data/intro.ipynb'
    });
  });

  it('swallows docmanager:open rejections without surfacing as unhandled', async () => {
    const execute = jest.fn().mockRejectedValue(new Error('not found'));
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      render(
        <MarkdownLink app={fakeApp(execute)} baseDir="" href="missing.md">
          missing
        </MarkdownLink>
      );
      fireEvent.click(screen.getByRole('link'));
      await waitFor(() => expect(warn).toHaveBeenCalled());
    } finally {
      warn.mockRestore();
    }
  });

  it('renders fragment-only links as plain text', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href="#claude-mode">
        section
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText('section')).toBeInTheDocument();
  });

  it('treats scheme-relative URLs as external (SafeAnchor handles the block)', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href="//example.com/path">
        click
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('falls back to the resolved path when the LLM-supplied title carries bidi-override codepoints', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir=""
        href="README.md"
        title={'docs\u202E.gpj'}
      >
        the README
      </MarkdownLink>
    );
    // The dangerous title is dropped; hover preview defaults to the
    // (already-validated) resolved path so the user still sees the
    // intended target.
    expect(screen.getByRole('link')).toHaveAttribute('title', 'README.md');
  });

  it('blocks workspace-relative paths that resolve outside the workspace', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir="notebooks"
        href="../../../etc/passwd"
      >
        click
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(/link blocked/)).toHaveClass('nbi-sr-only');
    expect(execute).not.toHaveBeenCalled();
  });

  it('blocks absolute paths', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href="/etc/passwd">
        click
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(execute).not.toHaveBeenCalled();
  });

  it('blocks scheme-unmask via C0 controls in href when baseDir is empty', () => {
    // PathExt.join('', 'java\tscript:alert(1)') returns the input
    // unchanged; the WHATWG URL parser strips the tab during scheme
    // recognition and ends up interpreting the result as javascript:.
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir=""
        href="java	script:alert(1)"
      >
        click
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(execute).not.toHaveBeenCalled();
  });

  it('blocks a resolved path that carries dangerous codepoints', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href={'READ\u202EME.md'}>
        the README
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(execute).not.toHaveBeenCalled();
  });

  it('blocks empty href (react-markdown strips javascript: to empty)', () => {
    // react-markdown's built-in urlTransform replaces unsafe schemes with
    // an empty string before our override sees them; without this case
    // the workspace-relative branch would render an inert `<a href="#">`
    // that confuses the user.
    const execute = jest.fn();
    render(
      <MarkdownLink app={fakeApp(execute)} baseDir="" href="">
        click
      </MarkdownLink>
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(/link blocked/)).toHaveClass('nbi-sr-only');
    expect(execute).not.toHaveBeenCalled();
  });

  it('passes through a clean workspace-relative title', () => {
    const execute = jest.fn();
    render(
      <MarkdownLink
        app={fakeApp(execute)}
        baseDir=""
        href="README.md"
        title="See the project README"
      >
        the README
      </MarkdownLink>
    );
    expect(screen.getByRole('link')).toHaveAttribute(
      'title',
      'See the project README'
    );
  });
});
