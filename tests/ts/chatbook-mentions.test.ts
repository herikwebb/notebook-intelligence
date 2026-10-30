// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  applyChatbookMention,
  chatbookMentionToken,
  detectChatbookMentionTrigger,
  isChatbookMentionMenuKey
} from '../../src/chatbook-mentions';

describe('chatbook filesystem mentions', () => {
  it('detects a mention at start or after whitespace', () => {
    expect(detectChatbookMentionTrigger('@dat', 4)).toEqual({
      from: 0,
      to: 4,
      query: 'dat'
    });
    expect(detectChatbookMentionTrigger('load @docs/gu', 13)).toEqual({
      from: 5,
      to: 13,
      query: 'docs/gu'
    });
    expect(detectChatbookMentionTrigger('summarize (@fi', 14)).toEqual({
      from: 11,
      to: 14,
      query: 'fi'
    });
  });

  it('does not treat email addresses or completed mentions as triggers', () => {
    expect(detectChatbookMentionTrigger('person@example.com', 18)).toBeNull();
    expect(
      detectChatbookMentionTrigger('use @file:data.csv next', 23)
    ).toBeNull();
  });

  it('replaces the active query with an opaque mention token', () => {
    const text = 'load @dat then plot';
    const trigger = detectChatbookMentionTrigger(text, 9);
    expect(trigger).not.toBeNull();
    expect(applyChatbookMention(text, trigger!, 'file:data.csv')).toBe(
      'load @file:data.csv then plot'
    );
  });

  it('quotes a picked path that contains whitespace', () => {
    // Unquoted, the token would end at the space and name `data/my`.
    const text = 'load @my then plot';
    const trigger = detectChatbookMentionTrigger(text, 8);
    expect(applyChatbookMention(text, trigger!, 'file:data/my notes.md')).toBe(
      'load @file:"data/my notes.md" then plot'
    );
  });

  it('quotes only values an unquoted token would cut short', () => {
    expect(chatbookMentionToken('file:data.csv')).toBe('@file:data.csv');
    expect(chatbookMentionToken('dir:My Folder')).toBe('@dir:"My Folder"');
    expect(chatbookMentionToken('ext:catalog:Q3 orders')).toBe(
      '@ext:"catalog:Q3 orders"'
    );
    // An unquoted token also ends at `@`, as in `logo@2x.png`, and at the
    // separator controls Python treats as whitespace.
    expect(chatbookMentionToken('file:a\u001cb')).toBe('@file:"a\u001cb"');
    expect(chatbookMentionToken('file:img/logo@2x.png')).toBe(
      '@file:"img/logo@2x.png"'
    );
    // The quoted form cannot hold a quote or a line break, so such a value is
    // left alone.
    expect(chatbookMentionToken('file:say "hi" now.md')).toBe(
      '@file:say "hi" now.md'
    );
    expect(chatbookMentionToken('ext:catalog:a\u2028b c')).toBe(
      '@ext:catalog:a\u2028b c'
    );
  });

  it('claims navigation keys but leaves modified shortcuts alone', () => {
    const key = (
      name: string,
      modifiers: Partial<KeyboardEvent> = {}
    ): Parameters<typeof isChatbookMentionMenuKey>[0] => ({
      key: name,
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      ...modifiers
    });
    expect(isChatbookMentionMenuKey(key('Tab'))).toBe(true);
    expect(isChatbookMentionMenuKey(key('Enter'))).toBe(true);
    expect(isChatbookMentionMenuKey(key('ArrowDown'))).toBe(true);
    expect(isChatbookMentionMenuKey(key('Tab', { shiftKey: true }))).toBe(
      false
    );
    expect(isChatbookMentionMenuKey(key('Enter', { shiftKey: true }))).toBe(
      false
    );
    expect(isChatbookMentionMenuKey(key('a'))).toBe(false);
  });
});
