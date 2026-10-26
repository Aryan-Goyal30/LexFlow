import { useQuery } from '@tanstack/react-query';
import { lexflowApi } from '../services/api/lexflow';

/**
 * Whether this server runs the isolated demo database (Milestone 1). The
 * screens offer fictional demo clients and cases only when `verified` is true;
 * the server checks the connected database again on every such request.
 */
export function useDemoStatus() {
  return useQuery({
    queryKey: ['demo'] as const,
    queryFn: () => lexflowApi.demoStatus(),
    staleTime: 60_000,
    retry: false,
  });
}
