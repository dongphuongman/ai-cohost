import type { SuggestionAction, WSSuggestion } from '@/types/messages';

export interface HistoryEntry {
  suggestion: WSSuggestion;
  action: SuggestionAction;
  actionAt: Date;
}

const BADGE_LABELS: Record<SuggestionAction, string> = {
  sent: 'Đã gửi',
  pasted_not_sent: 'Đã dán',
  read: 'Đã đọc',
  dismissed: 'Đã bỏ',
  edited: 'Đã sửa',
};

interface Props {
  entries: HistoryEntry[];
}

export function HistoryList({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <div class="aco-history">
        <div class="aco-history-empty">Chưa có lịch sử gợi ý</div>
      </div>
    );
  }

  return (
    <div class="aco-history">
      {entries.map((entry) => (
        <div class="aco-history-item" key={entry.suggestion.id}>
          <div class="aco-history-text" title={entry.suggestion.replyText}>
            <strong>{entry.suggestion.originalComment.externalUserName}:</strong>{' '}
            {entry.suggestion.replyText}
          </div>
          <span class={`aco-history-badge aco-badge-${entry.action}`}>
            {BADGE_LABELS[entry.action]}
          </span>
        </div>
      ))}
    </div>
  );
}
