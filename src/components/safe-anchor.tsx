// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { hasDangerousTextCodepoints, safeAnchorUri } from '../utils';
import { useTrans } from '../i18n';

type SafeAnchorProps = {
  href: string | undefined | null;
  children: React.ReactNode;
  title?: string;
  className?: string;
};

/**
 * The single render path for anchor elements driven by LLM / tool output.
 *
 * Runs `href` through `safeAnchorUri`, which mirrors the server-side
 * `safe_anchor_uri` allowlist (`http` / `https` / `mailto`) and rejects
 * dangerous codepoints. On accept it renders a `_blank` anchor with
 * `rel="noopener noreferrer"` and an SR-only "(opens in new tab)" suffix;
 * on reject it falls through to plain text plus an SR-only "(link
 * blocked)" note so screen readers can tell why the link disappeared.
 *
 * The `title` attribute is scrubbed for the same dangerous codepoints
 * the URI check rejects, since react-markdown forwards CommonMark
 * `[text](url "title")` titles to the rendered anchor and an LLM can
 * smuggle bidi-override or zero-width characters there to visually
 * impersonate the link target on hover.
 */
export function SafeAnchor({
  href,
  children,
  title,
  className
}: SafeAnchorProps): React.ReactElement {
  const trans = useTrans();
  const safeUri = safeAnchorUri(href ?? '');
  if (!safeUri) {
    return (
      <span className={className}>
        {children}
        <span className="nbi-sr-only"> {trans.__('(link blocked)')}</span>
      </span>
    );
  }
  const safeTitle =
    typeof title === 'string' && !hasDangerousTextCodepoints(title)
      ? title
      : undefined;
  return (
    <a
      href={safeUri}
      target="_blank"
      rel="noopener noreferrer"
      title={safeTitle}
      className={className}
    >
      {children}
      <span className="nbi-sr-only"> {trans.__('(opens in new tab)')}</span>
    </a>
  );
}
