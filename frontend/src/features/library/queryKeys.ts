export const documentKeys = {
  list: (userId: number) => ['user', userId, 'documents'] as const,
}
