import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import type { WSSuggestion, SuggestionAction } from '@/types/messages';
import { getOverlayPosition, saveOverlayPosition } from '@/lib/storage';
import { SuggestionCard } from './SuggestionCard';
import { HistoryList, type HistoryEntry } from './HistoryList';

interface Props {
  onSendAction: (suggestionId: string, action: SuggestionAction, text?: string) => void;
  onSaveAsFaq: (question: string, answer: string) => void;
  onReadAloud: (text: string) => void;
  onPauseSession: () => void;
  onEndSession: () => void;
  platform: string;
}

export function Overlay({ onSendAction, onSaveAsFaq, onReadAloud, onPauseSession, onEndSession, platform }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 20 });
  const [currentSuggestion, setCurrentSuggestion] = useState<WSSuggestion | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [stats, setStats] = useState({ duration: 0, comments: 0, suggestions: 0 });
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const durationTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load saved position
  useEffect(() => {
    getOverlayPosition().then((pos) => setPosition(pos));
  }, []);

  // Duration timer
  useEffect(() => {
    durationTimer.current = setInterval(() => {
      setStats((s) => ({ ...s, duration: s.duration + 1 }));
    }, 1000);
    return () => {
      if (durationTimer.current) clearInterval(durationTimer.current);
    };
  }, []);

  // Expose methods for content script to call
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      const { type, data } = e.detail;
      if (type === 'suggestion.new') {
        setCurrentSuggestion(data.suggestion);
        setStreamingText('');
        setIsStreaming(false);
        setStats((s) => ({ ...s, suggestions: s.suggestions + 1 }));
      } else if (type === 'suggestion.stream') {
        setIsStreaming(true);
        setStreamingText((prev) => prev + data.chunk);
      } else if (type === 'suggestion.complete') {
        // Finalize streaming into suggestion
        setIsStreaming(false);
        if (currentSuggestion && currentSuggestion.id === data.suggestion_id) {
          setCurrentSuggestion((s) =>
            s ? { ...s, replyText: streamingText || s.replyText } : s,
          );
          setStreamingText('');
        }
      } else if (type === 'comment.counted') {
        setStats((s) => ({ ...s, comments: s.comments + 1 }));
      }
    };

    window.addEventListener('aco-overlay-event', handler as EventListener);
    return () => window.removeEventListener('aco-overlay-event', handler as EventListener);
  }, [currentSuggestion, streamingText]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!currentSuggestion) return;
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        handleAction(currentSuggestion.id, 'sent');
      } else if (e.ctrlKey && e.key === ' ') {
        e.preventDefault();
        handleAction(currentSuggestion.id, 'read');
      } else if (e.ctrlKey && e.key === 'e') {
        e.preventDefault();
        // Edit mode handled inside SuggestionCard
      } else if (e.key === 'Escape') {
        handleAction(currentSuggestion.id, 'dismissed');
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [currentSuggestion]);

  const handleAction = useCallback(
    (suggestionId: string, action: SuggestionAction, editedText?: string) => {
      if (currentSuggestion && currentSuggestion.id === suggestionId) {
        setHistory((h) => [
          { suggestion: currentSuggestion, action, actionAt: new Date() },
          ...h,
        ]);
        setCurrentSuggestion(null);
      }
      onSendAction(suggestionId, action, editedText);
    },
    [currentSuggestion, onSendAction],
  );

  // Drag handling
  const onMouseDown = useCallback(
    (e: MouseEvent) => {
      dragging.current = true;
      dragOffset.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      };
    },
    [position],
  );

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const newPos = {
        x: e.clientX - dragOffset.current.x,
        y: e.clientY - dragOffset.current.y,
      };
      setPosition(newPos);
    };
    const onMouseUp = () => {
      if (dragging.current) {
        dragging.current = false;
        saveOverlayPosition(position);
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [position]);

  const formatDuration = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  // Build suggestion with streaming text
  const displaySuggestion = currentSuggestion
    ? streamingText
      ? { ...currentSuggestion, replyText: streamingText }
      : currentSuggestion
    : null;

  return (
    <div
      id="ai-cohost-overlay"
      ref={overlayRef}
      class={collapsed ? 'aco-collapsed' : ''}
      style={{ left: `${position.x}px`, top: `${position.y}px` }}
    >
      <div class="aco-panel">
        {/* Header */}
        <div class="aco-header" onMouseDown={onMouseDown}>
          <div class="aco-header-left">
            <span class="aco-logo">AI Co-host</span>
            <span class="aco-live-dot" />
            <span style="font-size:12px;opacity:0.8">{platform}</span>
          </div>
          <div class="aco-header-actions">
            <button
              class="aco-header-btn"
              onClick={() => setCollapsed(!collapsed)}
              title={collapsed ? 'Mở rộng' : 'Thu nhỏ'}
            >
              {collapsed ? '▼' : '▲'}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div class="aco-stats">
          <div class="aco-stat-item">
            <span class="aco-stat-value">{formatDuration(stats.duration)}</span>
            <span>Thời gian</span>
          </div>
          <div class="aco-stat-item">
            <span class="aco-stat-value">{stats.comments}</span>
            <span>Comments</span>
          </div>
          <div class="aco-stat-item">
            <span class="aco-stat-value">{stats.suggestions}</span>
            <span>Gợi ý</span>
          </div>
        </div>

        {/* Suggestion */}
        {!collapsed && (
          <>
            <SuggestionCard
              suggestion={displaySuggestion}
              isStreaming={isStreaming}
              onAction={handleAction}
              onSaveAsFaq={onSaveAsFaq}
              onReadAloud={onReadAloud}
            />
            <HistoryList entries={history} />
            <div class="aco-session-controls">
              <button class="aco-btn aco-btn-secondary" onClick={onPauseSession} style="flex:1">
                Tạm dừng
              </button>
              <button
                class="aco-btn aco-btn-secondary"
                onClick={onEndSession}
                style="flex:1;color:#EF4444"
              >
                Kết thúc
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
