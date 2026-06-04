import {
  IToolCallStreamItem,
  upsertToolCallContent
} from '../../src/tool-call-stream';
import { ResponseStreamDataType } from '../../src/tokens';

const created = new Date('2026-01-01T00:00:00Z');

describe('upsertToolCallContent', () => {
  it('pushes a new card on the first emission', () => {
    const contents: IToolCallStreamItem[] = [];
    upsertToolCallContent(
      contents,
      { id: 'a', title: 'Reading file', kind: 'read', status: 'in_progress' },
      created
    );
    expect(contents).toHaveLength(1);
    expect(contents[0].type).toBe(ResponseStreamDataType.ToolCall);
    expect(contents[0].content.status).toBe('in_progress');
  });

  it('updates the same card in place on the second emission (no duplicate row)', () => {
    const contents: IToolCallStreamItem[] = [];
    upsertToolCallContent(
      contents,
      { id: 'a', title: 'Reading file', kind: 'read', status: 'in_progress' },
      created
    );
    upsertToolCallContent(
      contents,
      { id: 'a', title: 'Reading file', kind: 'read', status: 'completed' },
      created
    );
    expect(contents).toHaveLength(1);
    expect(contents[0].content.status).toBe('completed');
  });

  it('keeps distinct ids as distinct cards', () => {
    const contents: IToolCallStreamItem[] = [];
    upsertToolCallContent(
      contents,
      { id: 'a', title: 'Read', kind: 'read', status: 'in_progress' },
      created
    );
    upsertToolCallContent(
      contents,
      { id: 'b', title: 'Edit', kind: 'edit', status: 'in_progress' },
      created
    );
    expect(contents).toHaveLength(2);
    expect(contents.map(c => c.content.id)).toEqual(['a', 'b']);
  });

  it('does not merge into a non-tool-call item that shares the id', () => {
    // A Markdown item that happens to carry a matching id must not be treated
    // as the tool call's card; the type guard prevents that.
    const contents: IToolCallStreamItem[] = [
      {
        id: 'x',
        type: ResponseStreamDataType.Markdown,
        content: { id: 'a' },
        created
      }
    ];
    upsertToolCallContent(
      contents,
      { id: 'a', title: 'Read', kind: 'read', status: 'in_progress' },
      created
    );
    expect(contents).toHaveLength(2);
    expect(contents[1].type).toBe(ResponseStreamDataType.ToolCall);
  });
});
