export type ChatRole = 'user' | 'assistant';

import { SHELL_COPY } from './copy';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
}

export const CHAT_RECOMMENDED_MODEL_ID = 'recommended' as const;

export const CHAT_MODEL_OPTIONS = [
  { id: CHAT_RECOMMENDED_MODEL_ID, label: 'Recommended' },
  { id: 'sonnet-4-6', label: 'Sonnet 4.6' },
  { id: 'sonnet-4-5', label: 'Sonnet 4.5' },
  { id: 'opus-4-8', label: 'Opus 4.8' },
  { id: 'opus-4-7', label: 'Opus 4.7' },
  { id: 'opus-4-6', label: 'Opus 4.6' },
  { id: 'opus-4-5', label: 'Opus 4.5' },
  { id: 'haiku-4-5', label: 'Haiku 4.5' },
  { id: 'gemini-3-5-flash', label: 'Gemini 3.5 Flash' },
  { id: 'gemini-3-1-pro', label: 'Gemini 3.1 Pro' },
  { id: 'gemini-3-1-flash-lite', label: 'Gemini 3.1 Flash Lite' },
  { id: 'gemini-3-flash', label: 'Gemini 3 Flash' },
  { id: 'gpt-5-5', label: 'GPT-5.5' },
  { id: 'gpt-5-4-mini', label: 'GPT-5.4 Mini' },
  { id: 'gpt-5-4', label: 'GPT-5.4' },
  { id: 'gpt-5-3-codex', label: 'GPT-5.3 Codex' },
  { id: 'gpt-5-2', label: 'GPT-5.2' },
] as const;

export type ChatModelId = (typeof CHAT_MODEL_OPTIONS)[number]['id'];

export type ChatSpecificModelId = Exclude<ChatModelId, typeof CHAT_RECOMMENDED_MODEL_ID>;

export const CHAT_SPECIFIC_MODEL_OPTIONS = CHAT_MODEL_OPTIONS.filter(
  (option): option is (typeof CHAT_MODEL_OPTIONS)[number] & { id: ChatSpecificModelId } =>
    option.id !== CHAT_RECOMMENDED_MODEL_ID,
);

export const DEFAULT_CHAT_SPECIFIC_MODEL_ID: ChatSpecificModelId = 'sonnet-4-6';

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  draft: string;
  modelId: ChatSpecificModelId;
  recommendedEnabled: boolean;
  isTyping: boolean;
}

let sessionCounter = 0;
let messageCounter = 0;

const CHAT_TAB_PREVIEW_MAX = 48;

export function createChatSessionTitle(): string {
  return SHELL_COPY.chatSessionTabLabel;
}

/** Tab label: "New Agent" until the first user message, then a preview of the latest question. */
export function getChatSessionTabPreview(session: ChatSession): string {
  const userMessages = session.messages.filter((message) => message.role === 'user');
  if (userMessages.length === 0) {
    return SHELL_COPY.chatSessionTabLabel;
  }

  const latest = userMessages[userMessages.length - 1].content.trim();
  if (!latest) {
    return SHELL_COPY.chatSessionTabLabel;
  }

  if (latest.length <= CHAT_TAB_PREVIEW_MAX) {
    return latest;
  }

  return `${latest.slice(0, CHAT_TAB_PREVIEW_MAX)}…`;
}

export function createChatSession(): ChatSession {
  sessionCounter += 1;
  return {
    id: `chat-session-${sessionCounter}`,
    title: createChatSessionTitle(),
    messages: [],
    draft: '',
    modelId: DEFAULT_CHAT_SPECIFIC_MODEL_ID,
    recommendedEnabled: true,
    isTyping: false,
  };
}

export function createChatMessage(role: ChatRole, content: string): ChatMessage {
  messageCounter += 1;
  return {
    id: `chat-msg-${messageCounter}`,
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

export function buildStubAssistantReply(userMessage: string): string {
  const trimmed = userMessage.trim();
  if (!trimmed) {
    return 'Send a message to preview the assistant conversation layout.';
  }

  return `This workspace assistant is not connected to a model provider yet. When enabled, responses to “${trimmed.slice(0, 120)}${trimmed.length > 120 ? '…' : ''}” will appear here with tenant-scoped context.`;
}
