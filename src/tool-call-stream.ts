import { UUID } from '@lumino/coreutils';
import { ResponseStreamDataType } from './tokens';

/**
 * The subset of a chat message's stream-content item this helper needs. A
 * structural subset of `IChatMessageContent` (defined in chat-sidebar) so it
 * can be unit-tested without importing the sidebar (and creating a cycle).
 */
export interface IToolCallStreamItem {
  id: string;
  type: ResponseStreamDataType;
  content: any;
  created: Date;
}

/**
 * Merge a streamed tool-call payload into `contents` by its tool-call id.
 *
 * A tool call streams twice under one id (once when it starts, once when it
 * finishes). The first emission pushes a new card; the second updates that
 * card's content (its status) in place, so the call stays a single persistent
 * row rather than appending a duplicate. Mutates `contents`.
 */
export function upsertToolCallContent(
  contents: IToolCallStreamItem[],
  content: { id: string; [key: string]: any },
  created: Date
): void {
  const existing = contents.find(
    c =>
      c.type === ResponseStreamDataType.ToolCall &&
      c.content?.id === content?.id
  );
  if (existing) {
    existing.content = content;
  } else {
    contents.push({
      id: UUID.uuid4(),
      type: ResponseStreamDataType.ToolCall,
      content,
      created
    });
  }
}
