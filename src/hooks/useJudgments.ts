import { useQuery } from '@tanstack/react-query';
import { lexflowApi, type JudgmentFilters, type JudgmentQuery } from '../services/api/lexflow';

/**
 * The judgment collection (Phase 4). Every query is keyed by all of its
 * parameters and keeps no placeholder data, so a result is only ever shown
 * for the search that produced it: while a new search runs, the old results
 * are gone, never presented as the answer to the new query.
 */

/** Totals, courts, years and which search modes work. */
export function useJudgmentFacets() {
  return useQuery({
    queryKey: ['judgments', 'facets'],
    queryFn: lexflowApi.judgmentFacets,
    staleTime: 60_000,
  });
}

/** One page of the collection, newest first. */
export function useJudgmentList(filters: JudgmentFilters, page: number, enabled = true) {
  return useQuery({
    queryKey: ['judgments', 'list', filters, page],
    queryFn: () => lexflowApi.listJudgments(filters, page),
    enabled,
    retry: false,
  });
}

/** A search, or nothing while no query has been submitted. */
export function useJudgmentSearch(query: JudgmentQuery | null) {
  return useQuery({
    queryKey: ['judgments', 'search', query],
    queryFn: () => lexflowApi.searchJudgments(query as JudgmentQuery),
    enabled: query !== null,
    retry: false,
  });
}

export function useJudgment(judgmentId: string) {
  return useQuery({
    queryKey: ['judgments', judgmentId],
    queryFn: () => lexflowApi.judgment(judgmentId),
    retry: false,
  });
}

export function useJudgmentText(judgmentId: string, section: number) {
  return useQuery({
    queryKey: ['judgments', judgmentId, 'text', section],
    queryFn: () => lexflowApi.judgmentText(judgmentId, section),
    retry: false,
  });
}
