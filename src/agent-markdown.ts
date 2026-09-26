// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

/**
 * Markdown an agent writes into a notebook cell is rendered by JupyterLab
 * as soon as the cell lands, and again whenever the notebook is opened.
 * An image, or any raw HTML element with a media source, is fetched at
 * render time with no user interaction, so the request target and query
 * string are chosen by the model, which content it was asked to read can
 * steer. The chat sidebar already renders model markdown without fetching
 * image sources (see MarkdownImage); this applies the same policy at the
 * point where agent markdown becomes cell source.
 *
 * Markdown images become links, which need a click and go through the
 * renderer's href scheme check. Raw HTML elements that fetch on render are
 * shown as text by escaping their opening bracket. Fenced code blocks and
 * inline code spans are left untouched, as they never render as HTML.
 */

// Elements the notebook sanitizer keeps whose rendering issues a request:
// `src` and `poster` are exempt from its scheme validation, and `style`
// may carry a background image. The rest never render, but escaping them
// too keeps the source readable rather than silently dropped.
const MEDIA_TAG_RE =
  /<(?=\/?(?:img|picture|source|video|audio|track|embed|object|iframe|frame|link|meta|base|input|image|use|svg|style)\b)/gi;

// Any element carrying a `style` attribute with a `url(` value.
const STYLE_URL_TAG_RE =
  /<(?=[a-z][\w-]*\b(?:[^>"']|"[^"]*"|'[^']*')*\bstyle\s*=\s*(?:"[^"]*url\s*\(|'[^']*url\s*\())/gi;

// `![` that is not backslash-escaped: an inline or reference-style image.
const IMAGE_OPEN_RE = /(^|[^\\])!\[/g;

// Backtick-delimited code spans, matched by run length so a span can
// contain shorter runs.
const CODE_SPAN_RE = /(`+)[\s\S]*?\1/g;

const FENCE_RE = /^ {0,3}(`{3,}|~{3,})/;

function disarmSegment(text: string): string {
  return text
    .replace(IMAGE_OPEN_RE, '$1[')
    .replace(MEDIA_TAG_RE, '&lt;')
    .replace(STYLE_URL_TAG_RE, '&lt;');
}

function disarmOutsideCodeSpans(line: string): string {
  let result = '';
  let last = 0;
  for (const match of line.matchAll(CODE_SPAN_RE)) {
    const start = match.index ?? 0;
    result += disarmSegment(line.slice(last, start)) + match[0];
    last = start + match[0].length;
  }
  return result + disarmSegment(line.slice(last));
}

/**
 * Rewrite agent-supplied markdown so that rendering it fetches nothing.
 *
 * Returns the source unchanged when it contains no image or media element.
 */
export function disarmAgentMarkdown(source: string): string {
  if (typeof source !== 'string' || source.length === 0) {
    return source;
  }
  const lines = source.split('\n');
  let fence: string | null = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const opener = FENCE_RE.exec(line);
    if (fence === null) {
      if (opener) {
        fence = opener[1];
        continue;
      }
      lines[i] = disarmOutsideCodeSpans(line);
    } else if (
      opener &&
      opener[1][0] === fence[0] &&
      opener[1].length >= fence.length
    ) {
      fence = null;
    }
  }
  return lines.join('\n');
}
