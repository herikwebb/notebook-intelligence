// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { hasDangerousTextCodepoints } from '../utils';

type MarkdownImageProps = {
  alt?: unknown;
  title?: unknown;
};

/**
 * The single render path for image nodes driven by LLM / tool output.
 *
 * Anchors are already funneled through `MarkdownLink` / `SafeAnchor` so a
 * chat link can never navigate the shell or carry a dangerous scheme, but
 * an image is worse than a link: the browser fetches `src` the moment the
 * node renders, with no click. A CommonMark `![](https://host/p?d=...)`
 * emitted by the model is therefore a zero-interaction outbound request
 * whose URL the model chooses, which is exactly the shape an indirect
 * prompt injection needs to move context off the machine.
 *
 * No `src` reaches the DOM. Every markdown image renders as inert text —
 * the alt text when the model supplied one, plus an SR-only "(image
 * blocked)" note so screen readers can tell why nothing appeared. That
 * costs no real functionality: raw HTML never renders (no `rehype-raw`),
 * react-markdown's `urlTransform` already strips `data:` URIs, and
 * notebook figures reach the sidebar over the dedicated image response
 * stream rather than as chat markdown.
 *
 * `alt` and `title` are scrubbed for the same dangerous codepoints
 * `SafeAnchor` rejects, since an LLM can smuggle bidi-override or
 * zero-width characters through them to impersonate other chat text.
 */
export function MarkdownImage({
  alt,
  title
}: MarkdownImageProps): React.ReactElement {
  const safeAlt =
    typeof alt === 'string' && alt !== '' && !hasDangerousTextCodepoints(alt)
      ? alt
      : undefined;
  const safeTitle =
    typeof title === 'string' &&
    title !== '' &&
    !hasDangerousTextCodepoints(title)
      ? title
      : undefined;
  return (
    <span className="nbi-blocked-image" title={safeTitle}>
      {safeAlt}
      <span className="nbi-sr-only"> (image blocked)</span>
    </span>
  );
}
