import { useState, useRef } from 'preact/hooks';
import type { WSSuggestion, SuggestionAction } from '@/types/messages';

interface Props {
  suggestion: WSSuggestion | null;
  isStreaming?: boolean;
  onAction: (suggestionId: string, action: SuggestionAction, editedText?: string) => void;
  onSaveAsFaq?: (question: string, answer: string) => void;
  onReadAloud?: (text: string) => void;
}

export function SuggestionCard({ suggestion, isStreaming, onAction, onSaveAsFaq, onReadAloud }: Props) {
  const [editing, setEditing] = useState(false);
  const [saveAsFaq, setSaveAsFaq] = useState(false);
  const replyRef = useRef<HTMLDivElement>(null);

  if (!suggestion) {
    return (
      <div class="aco-suggestion">
        <div style="text-align:center;padding:20px;color:#999;font-size:13px;">
          Đang chờ comment mới...
        </div>
      </div>
    );
  }

  const getEditedText = (): string =>
    (editing && replyRef.current
      ? replyRef.current.textContent ?? suggestion.replyText
      : suggestion.replyText);

  const handleSend = () => {
    if (isStreaming) return;
    const text = getEditedText();
    const action: SuggestionAction = editing ? 'edited' : 'sent';
    onAction(suggestion.id, action, text);
    if (editing && saveAsFaq && onSaveAsFaq) {
      onSaveAsFaq(suggestion.originalComment.text, text);
    }
    setEditing(false);
    setSaveAsFaq(false);
  };

  const handleEdit = () => {
    setEditing(!editing);
    setSaveAsFaq(false);
    if (!editing) {
      setTimeout(() => replyRef.current?.focus(), 50);
    }
  };

  const handleDismiss = () => {
    onAction(suggestion.id, 'dismissed');
    setEditing(false);
    setSaveAsFaq(false);
  };

  const handleRead = () => {
    if (onReadAloud) {
      onReadAloud(suggestion.replyText);
    }
    onAction(suggestion.id, 'read');
  };

  return (
    <div class="aco-suggestion">
      <div class="aco-comment-display">
        <div class="aco-comment-user">{suggestion.originalComment.externalUserName}</div>
        <div class="aco-comment-text">{suggestion.originalComment.text}</div>
      </div>

      <div
        ref={replyRef}
        class={`aco-reply-preview${isStreaming ? ' aco-streaming' : ''}`}
        contentEditable={editing}
        onKeyDown={(e) => {
          if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            handleSend();
          }
        }}
      >
        {suggestion.replyText}
        {isStreaming && <span class="aco-cursor" />}
      </div>

      {editing && (
        <label class="aco-faq-checkbox">
          <input
            type="checkbox"
            checked={saveAsFaq}
            onChange={(e) => setSaveAsFaq((e.target as HTMLInputElement).checked)}
          />
          <span>Lưu làm FAQ cho sản phẩm này</span>
        </label>
      )}

      <div class="aco-actions">
        <button
          class="aco-btn aco-btn-primary"
          onClick={handleSend}
          title="Ctrl+Enter"
          disabled={isStreaming}
        >
          Gửi<span class="aco-shortcut">⌃↵</span>
        </button>
        <button class="aco-btn aco-btn-secondary" onClick={handleRead} title="Ctrl+Space" disabled={isStreaming}>
          Đọc<span class="aco-shortcut">⌃␣</span>
        </button>
        <button class="aco-btn aco-btn-secondary" onClick={handleEdit} title="Ctrl+E" disabled={isStreaming}>
          {editing ? 'Xong' : 'Sửa'}<span class="aco-shortcut">⌃E</span>
        </button>
        <button class="aco-btn aco-btn-secondary" onClick={handleDismiss} title="Esc">
          Bỏ
        </button>
      </div>
    </div>
  );
}
