import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiService } from '../services/ai/aiService';
import { ApiError } from '../services/api/client';
import type { AnalysisReview, AnalysisReviewInput, AnalysisReviewList } from '../types/ai';
import { analysisKeys } from './useCaseAnalysis';
import { queryKeys } from './useCases';

/**
 * Lawyer review of AI findings (Phase 6). Pages use these hooks, never the service.
 *
 * Guarantees:
 * - a decision appears only after the server has stored it (no optimistic
 *   "accepted" state), and the counts are taken from the server's answer;
 * - when the finding was reviewed again meanwhile (409), the list is fetched
 *   again so the reviewer sees the current decision before trying again;
 * - reviews are kept under the key of their run, so a slow answer for one run
 *   never shows on another.
 */

export const reviewKeys = {
  run: (caseId: string, runId: string) => [...analysisKeys.run(caseId, runId), 'reviews'] as const,
  history: (caseId: string, runId: string, findingId: string) =>
    [...analysisKeys.run(caseId, runId), 'reviews', findingId, 'history'] as const,
};

export function useFindingReviews(caseId: string, runId: string) {
  return useQuery({
    queryKey: reviewKeys.run(caseId, runId),
    queryFn: async () => {
      const list = await aiService.reviews(caseId, runId);
      if (list.runId !== runId) {
        throw new Error('The server returned the reviews of a different analysis.');
      }
      return list;
    },
    retry: false,
  });
}

export function useReviewHistory(
  caseId: string,
  runId: string,
  findingId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: reviewKeys.history(caseId, runId, findingId),
    queryFn: () => aiService.reviewHistory(caseId, runId, findingId),
    enabled,
    retry: false,
  });
}

/** The list with one finding's stored decision replaced, and the counts recomputed. */
export function withReview(list: AnalysisReviewList, review: AnalysisReview): AnalysisReviewList {
  const items = list.items.map((i) => (i.findingId === review.findingId ? review : i));
  const count = (status: AnalysisReview['status']) =>
    items.filter((i) => i.status === status).length;
  return {
    ...list,
    items,
    summary: {
      total: items.length,
      unreviewed: count('unreviewed'),
      accepted: count('accepted'),
      edited: count('edited'),
      rejected: count('rejected'),
    },
  };
}

export function useReviewFinding(caseId: string, runId: string) {
  const queryClient = useQueryClient();
  const key = reviewKeys.run(caseId, runId);
  return useMutation({
    mutationFn: ({ findingId, input }: { findingId: string; input: AnalysisReviewInput }) =>
      aiService.review(caseId, runId, findingId, input),
    onSuccess: (review) => {
      queryClient.setQueryData<AnalysisReviewList>(key, (list) =>
        list ? withReview(list, review) : list,
      );
      void queryClient.invalidateQueries({
        queryKey: reviewKeys.history(caseId, runId, review.findingId),
      });
      // The matter timeline shows review actions.
      void queryClient.invalidateQueries({ queryKey: queryKeys.case(caseId), exact: true });
      // Phase 7 demo: what an assessment may use (accepted findings) changed.
      void queryClient.invalidateQueries({
        queryKey: [...analysisKeys.run(caseId, runId), 'assessments'],
        exact: true,
      });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: key, exact: true });
      }
    },
  });
}

export function useExportBrief(caseId: string, runId: string) {
  return useMutation({
    mutationFn: () => aiService.exportBrief(caseId, runId),
  });
}
