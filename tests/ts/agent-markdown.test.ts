// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { disarmAgentMarkdown } from '../../src/agent-markdown';

describe('disarmAgentMarkdown', () => {
  it('turns an inline image into a link', () => {
    expect(
      disarmAgentMarkdown('See ![chart](https://example.test/c?d=c2VjcmV0)')
    ).toBe('See [chart](https://example.test/c?d=c2VjcmV0)');
  });

  it('turns reference-style and adjacent images into links', () => {
    expect(disarmAgentMarkdown('![a][ref]![b](x)\n\n[ref]: https://x')).toBe(
      '[a][ref][b](x)\n\n[ref]: https://x'
    );
  });

  it('leaves an escaped image marker alone', () => {
    expect(disarmAgentMarkdown('literal \\![not an image](x)')).toBe(
      'literal \\![not an image](x)'
    );
  });

  it('escapes raw HTML elements that fetch when rendered', () => {
    expect(
      disarmAgentMarkdown('<img src="https://example.test/p?k=v" alt="">')
    ).toBe('&lt;img src="https://example.test/p?k=v" alt="">');
    expect(disarmAgentMarkdown('<IMG SRC=x>')).toBe('&lt;IMG SRC=x>');
    expect(
      disarmAgentMarkdown(
        '<video poster="https://x/p" src="https://x/v"></video>'
      )
    ).toBe('&lt;video poster="https://x/p" src="https://x/v">&lt;/video>');
    expect(disarmAgentMarkdown('<audio src=https://x/a>')).toBe(
      '&lt;audio src=https://x/a>'
    );
    expect(
      disarmAgentMarkdown('<picture><source srcset="https://x/s"></picture>')
    ).toBe('&lt;picture>&lt;source srcset="https://x/s">&lt;/picture>');
    expect(disarmAgentMarkdown('<svg><image href="https://x/i"/></svg>')).toBe(
      '&lt;svg>&lt;image href="https://x/i"/>&lt;/svg>'
    );
  });

  it('escapes any element whose style carries a url()', () => {
    expect(
      disarmAgentMarkdown('<div style="background: url(https://x/b)">hi</div>')
    ).toBe('&lt;div style="background: url(https://x/b)">hi</div>');
    expect(
      disarmAgentMarkdown(
        "<span class='a' style='background-image:url( https://x )'>"
      )
    ).toBe("&lt;span class='a' style='background-image:url( https://x )'>");
  });

  it('leaves other HTML and links untouched', () => {
    const source =
      '<div style="color: red">**bold**</div>\n' +
      '<details><summary>More</summary>text</details>\n' +
      '[a link](https://example.test) and <br>\n' +
      '| a | b |\n|---|---|\n| 1 | 2 |';
    expect(disarmAgentMarkdown(source)).toBe(source);
  });

  it('leaves fenced code blocks and inline code alone', () => {
    const source =
      'Use `![alt](x)` or `<img src=x>` inline.\n' +
      '```html\n<img src="https://x/y">\n![img](z)\n```\n' +
      '~~~\n<video src=a>\n~~~\n' +
      'but not ![this](https://x/q)';
    expect(disarmAgentMarkdown(source)).toBe(
      'Use `![alt](x)` or `<img src=x>` inline.\n' +
        '```html\n<img src="https://x/y">\n![img](z)\n```\n' +
        '~~~\n<video src=a>\n~~~\n' +
        'but not [this](https://x/q)'
    );
  });

  it('closes a fence only with the same character and a long enough run', () => {
    const source = '````\n```\n<img src=a>\n````\n<img src=b>';
    expect(disarmAgentMarkdown(source)).toBe(
      '````\n```\n<img src=a>\n````\n&lt;img src=b>'
    );
  });

  it('returns empty and non-string input unchanged', () => {
    expect(disarmAgentMarkdown('')).toBe('');
    expect(disarmAgentMarkdown(undefined as any)).toBe(undefined);
  });
});
