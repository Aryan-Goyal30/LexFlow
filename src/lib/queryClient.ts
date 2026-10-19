import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../services/api/client';

/**
 * Query defaults: retry network and server failures once, never 4xx answers
 * (a 404 or a validation error won't change by asking again).
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        retry: (failures, error) =>
          !(error instanceof ApiError && error.isClientError) && failures < 1,
      },
      mutations: { retry: false },
    },
  });
}
