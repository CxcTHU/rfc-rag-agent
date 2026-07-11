import { QueryClient } from '@tanstack/react-query'
import { shouldRetryApiQuery } from '@/lib/api/client'

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: shouldRetryApiQuery,
      },
      mutations: {
        retry: false,
      },
    },
  })
}
