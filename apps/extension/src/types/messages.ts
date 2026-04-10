// === Chrome message passing (background <-> content <-> popup) ===

export type ExtensionMessage =
  | { type: "GET_AUTH_TOKEN" }
  | { type: "SET_AUTH_TOKEN"; token: string; refreshToken: string }
  | { type: "LOGOUT" }
  | { type: "START_SESSION"; shopId: number; productIds: number[]; personaId: number; platform: string }
  | { type: "END_SESSION"; sessionId: string }
  | { type: "SESSION_STARTED"; sessionId: string }
  | { type: "SESSION_ENDED"; sessionId: string }
  | { type: "NEW_COMMENT"; comment: WSComment }
  | { type: "NEW_SUGGESTION"; suggestion: WSSuggestion }
  | { type: "SUGGESTION_ACTION"; suggestionId: string; action: SuggestionAction; editedText?: string }
  | { type: "SAVE_AS_FAQ"; productId: number; question: string; answer: string }
  | { type: "GENERATE_TTS"; text: string };

// === WebSocket protocol (extension <-> backend) ===

export interface WSComment {
  externalUserName: string;
  text: string;
  receivedAt: string;
  externalUserId?: string;
}

export interface WSSuggestion {
  id: string;
  replyText: string;
  originalComment: WSComment;
  confidence: number;
  createdAt: string;
}

export type SuggestionAction = "sent" | "pasted_not_sent" | "read" | "dismissed" | "edited";

// Client -> Server
export type WSClientMessage =
  | { type: "ping" }
  | { type: "session.start"; shop_id: number; products: number[]; persona_id: number; platform: string }
  | { type: "comment.new"; session_id: string; comment: WSComment }
  | { type: "suggestion.action"; session_id: string; suggestion_id: string; action: SuggestionAction; edited_text?: string }
  | { type: "session.end"; session_id: string };

// Server -> Client
export type WSServerMessage =
  | { type: "pong" }
  | { type: "session.started"; session_id: string }
  | { type: "suggestion.new"; suggestion: WSSuggestion }
  | { type: "suggestion.stream"; suggestion_id: string; chunk: string }
  | { type: "suggestion.complete"; suggestion_id: string }
  | { type: "error"; code: string; message: string };
