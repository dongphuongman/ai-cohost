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
  onToggleAutoReply?: (enabled: boolean) => void;
  platform: string;
  initialAutoReply?: boolean;
}

export function Overlay({ onSendAction, onSaveAsFaq, onReadAloud, onPauseSession, onEndSession, onToggleAutoReply, platform, initialAutoReply }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [autoReplyOn, setAutoReplyOn] = useState(initialAutoReply ?? false);
  const [pendingAutoReply, setPendingAutoReply] = useState<{ suggestion: WSSuggestion; deadline: Date } | null>(null);
  const [countdown, setCountdown] = useState(0);
  const autoReplyTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [position, setPosition] = useState({ x: 0, y: 20 });
  const [currentSuggestion, setCurrentSuggestion] = useState<WSSuggestion | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [stats, setStats] = useState({ duration: 0, comments: 0, suggestions: 0, hidden: 0 });
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
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
      } else if (type === 'comment.hidden') {
        setStats((s) => ({ ...s, hidden: s.hidden + 1 }));
      } else if (type === 'suggestion.auto_reply') {
        if (autoReplyOn) {
          setPendingAutoReply({ suggestion: data.suggestion, deadline: new Date(data.undo_deadline) });
          setCountdown(15);
          if (autoReplyTimerRef.current) clearInterval(autoReplyTimerRef.current);
          autoReplyTimerRef.current = setInterval(() => {
            setCountdown((prev) => {
              if (prev <= 1) {
                if (autoReplyTimerRef.current) clearInterval(autoReplyTimerRef.current);
                // Auto-send
                onSendAction(data.suggestion.id, 'sent');
                setPendingAutoReply(null);
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
        }
      } else if (type === 'comment.flagged') {
        // Show flagged comment in history with warning status
        const flaggedComment = data.comment;
        if (flaggedComment) {
          setHistory((h) => [
            {
              suggestion: {
                id: `flagged-${data.comment_id}`,
                replyText: '',
                originalComment: flaggedComment,
                confidence: 0,
                createdAt: new Date().toISOString(),
              },
              action: 'dismissed' as const,
              actionAt: new Date(),
              flagReason: data.reason,
            },
            ...h,
          ]);
        }
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
        if (pendingAutoReply) {
          if (autoReplyTimerRef.current) clearInterval(autoReplyTimerRef.current);
          onSendAction(pendingAutoReply.suggestion.id, 'dismissed');
          setPendingAutoReply(null);
        } else {
          handleAction(currentSuggestion.id, 'dismissed');
        }
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

        {/* Auto-reply indicator */}
        {autoReplyOn && (
          <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 12px;background:#5B47E0;font-size:11px;color:#fff;">
            <span>Auto-reply BAT</span>
            <button
              onClick={() => {
                setAutoReplyOn(false);
                if (autoReplyTimerRef.current) clearInterval(autoReplyTimerRef.current);
                setPendingAutoReply(null);
                onToggleAutoReply?.(false);
              }}
              style="padding:2px 8px;background:#EF4444;border-radius:4px;font-size:10px;font-weight:600;border:none;color:#fff;cursor:pointer;"
            >
              TAT NGAY
            </button>
          </div>
        )}

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
          {stats.hidden > 0 && (
            <div class="aco-stat-item">
              <span class="aco-stat-value">{stats.hidden}</span>
              <span>Ẩn</span>
            </div>
          )}
        </div>

        {/* Suggestion */}
        {!collapsed && (
          <>
            {/* Auto-reply countdown */}
            {pendingAutoReply && (
              <div style="padding:10px;margin:8px;background:rgba(91,71,224,0.1);border:1px solid rgba(91,71,224,0.3);border-radius:8px;">
                <div style="font-size:11px;color:#5B47E0;margin-bottom:6px;">Auto-reply trong {countdown}s</div>
                <div style="font-size:12px;color:#6B7280;margin-bottom:4px;">
                  {pendingAutoReply.suggestion.originalComment}
                </div>
                <div style="font-size:12px;background:#F3F4F6;border-radius:6px;padding:6px 8px;margin-bottom:8px;">
                  {pendingAutoReply.suggestion.replyText}
                </div>
                <div style="width:100%;background:#D1D5DB;border-radius:4px;height:4px;margin-bottom:8px;">
                  <div style={`width:${(countdown / 15) * 100}%;background:#5B47E0;height:4px;border-radius:4px;transition:width 1s linear;`} />
                </div>
                <button
                  onClick={() => {
                    if (autoReplyTimerRef.current) clearInterval(autoReplyTimerRef.current);
                    onSendAction(pendingAutoReply.suggestion.id, 'dismissed');
                    setPendingAutoReply(null);
                  }}
                  style="width:100%;padding:6px;background:#EF4444;color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;"
                >
                  HUY — Toi tu tra loi
                </button>
                <div style="text-align:center;font-size:10px;color:#9CA3AF;margin-top:4px;">Hoac nhan Esc</div>
              </div>
            )}

            <SuggestionCard
              suggestion={displaySuggestion}
              isStreaming={isStreaming}
              onAction={handleAction}
              onSaveAsFaq={onSaveAsFaq}
              onReadAloud={onReadAloud}
            />
            <HistoryList entries={history} />

            {showSummary ? (
              <div class="aco-session-summary" style="padding:12px;background:#F9FAFB;border-top:1px solid #E5E7EB;">
                <p style="font-weight:600;font-size:13px;margin-bottom:8px;">Tổng kết phiên live</p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;margin-bottom:10px;">
                  <div>Thời gian: <strong>{formatDuration(stats.duration)}</strong></div>
                  <div>Comments: <strong>{stats.comments}</strong></div>
                  <div>Gợi ý AI: <strong>{stats.suggestions}</strong></div>
                  <div>Đã gửi: <strong>{history.filter((h) => h.action === 'sent').length}</strong></div>
                  <div>Đã đọc: <strong>{history.filter((h) => h.action === 'read').length}</strong></div>
                  <div>Bỏ qua: <strong>{history.filter((h) => h.action === 'dismissed').length}</strong></div>
                </div>
                <div style="display:flex;gap:8px;">
                  <button class="aco-btn aco-btn-secondary" onClick={() => setShowSummary(false)} style="flex:1">
                    Quay lại
                  </button>
                  <button
                    class="aco-btn"
                    onClick={onEndSession}
                    style="flex:1;background:#EF4444;color:#fff;"
                  >
                    Xác nhận kết thúc
                  </button>
                </div>
              </div>
            ) : (
              <div class="aco-session-controls">
                <button class="aco-btn aco-btn-secondary" onClick={onPauseSession} style="flex:1">
                  Tạm dừng
                </button>
                <button
                  class="aco-btn aco-btn-secondary"
                  onClick={() => setShowSummary(true)}
                  style="flex:1;color:#EF4444"
                >
                  Kết thúc
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
