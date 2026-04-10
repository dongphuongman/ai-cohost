export type SuggestionStatus =
  | "suggested"
  | "sent"
  | "pasted_not_sent"
  | "read"
  | "dismissed"
  | "edited";

export interface LiveSession {
  id: number;
  uuid: string;
  shopId: number;
  platform: "facebook" | "tiktok" | "youtube" | "shopee" | "other";
  platformUrl: string | null;
  personaId: number | null;
  activeProductIds: number[];
  startedAt: string;
  endedAt: string | null;
  durationSeconds: number | null;
  status: string;
  commentsCount: number;
  suggestionsCount: number;
  sentCount: number;
}

export interface Comment {
  id: number;
  sessionId: number;
  externalUserName: string | null;
  text: string;
  receivedAt: string;
  intent: string | null;
  isSpam: boolean;
}

export interface Suggestion {
  id: number;
  commentId: number;
  text: string;
  editedText: string | null;
  status: SuggestionStatus;
  latencyMs: number | null;
  createdAt: string;
}
