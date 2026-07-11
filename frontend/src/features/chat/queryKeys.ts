export const conversationKeys = {
  list: (userId: number) => ['user', userId, 'conversations'] as const,
  messages: (userId: number, conversationId: number) =>
    ['user', userId, 'conversation', conversationId, 'messages'] as const,
}
