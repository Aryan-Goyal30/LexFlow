import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { lexflowApi } from '../services/api/lexflow';

/** The server refuses shorter queries (422), so none is sent. */
export const QUICK_SEARCH_MIN = 2;
/** How long typing must pause before a search is sent. */
export const QUICK_SEARCH_DELAY_MS = 250;

/** `value`, once it has stopped changing for `ms` milliseconds. */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * The top bar's quick search across cases, clients and documents. The server
 * matches names and numbers and applies the same visibility as the lists, so
 * nothing beyond the few matches is fetched. `q` is the query the results are
 * for; while it differs from what was typed, a search is pending.
 */
export function useGlobalSearch(text: string) {
  const q = useDebounced(text.trim(), QUICK_SEARCH_DELAY_MS);
  const query = useQuery({
    queryKey: ['search', q],
    queryFn: () => lexflowApi.quickSearch(q),
    enabled: q.length >= QUICK_SEARCH_MIN,
    retry: false,
    staleTime: 30_000,
  });
  return { query, q };
}
