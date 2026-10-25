import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiService } from '../services/ai/aiService';
import { ApiError } from '../services/api/client';
import type { AssessmentList, AssessmentReview, AssessmentReviewInput } from '../types/ai';
import { analysisKeys } from './useCaseAnalysis';
import { reviewKeys } from './useFindingReviews';

/**
 * Outcome assessments (Phase 7, synthetic engineering demo). Pages use these
 * hooks, never the service. Nothing is fetched unless the server's setup says
 * the feature is enabled, so with the flag off no request is ever made.
 *
 * As in Phase 6: an assessment or a decision appears only after the server
 * stored it; a stale decision (409) reloads the list; everything is kept under
 * the key of its run.
 */

export const assessmentKeys = {
  run: (caseId: string, runId: string) =>
    [...analysisKeys.run(caseId, runId), 'assessments'] as const,
  history: (caseId: string, runId: string, assessmentId: string) =>
    [...analysisKeys.run(caseId, runId), 'assessments', assessmentId, 'history'] as const,
};

export function useAssessments(caseId: string, runId: string, enabled: boolean) {
  return useQuery({
    queryKey: assessmentKeys.run(caseId, runId),
    queryFn: async () => {
      const list = await aiService.assessments(caseId, runId);
      if (list.runId !== runId) {
        throw new Error('The server returned the assessments of a different analysis.');
      }
      return list;
    },
    enabled,
    retry: false,
  });
}

export function useAssessmentHistory(
  caseId: string,
  runId: string,
  assessmentId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: assessmentKeys.history(caseId, runId, assessmentId),
    queryFn: () => aiService.assessmentHistory(caseId, runId, assessmentId),
    enabled,
    retry: false,
  });
}

export function useGenerateAssessment(caseId: string, runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => aiService.generateAssessment(caseId, runId),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: assessmentKeys.run(caseId, runId), exact: true }),
  });
}

/** The list with one assessment's stored decision replaced. */
export function withAssessmentReview(
  list: AssessmentList,
  assessmentId: string,
  review: AssessmentReview,
): AssessmentList {
  return {
    ...list,
    items: list.items.map((a) => (a.id === assessmentId ? { ...a, review } : a)),
  };
}

export function useReviewAssessment(caseId: string, runId: string) {
  const queryClient = useQueryClient();
  const key = assessmentKeys.run(caseId, runId);
  return useMutation({
    mutationFn: ({ assessmentId, input }: { assessmentId: string; input: AssessmentReviewInput }) =>
      aiService.reviewAssessment(caseId, runId, assessmentId, input),
    onSuccess: (review, { assessmentId }) => {
      queryClient.setQueryData<AssessmentList>(key, (list) =>
        list ? withAssessmentReview(list, assessmentId, review) : list,
      );
      void queryClient.invalidateQueries({
        queryKey: assessmentKeys.history(caseId, runId, assessmentId),
      });
      // An accepted assessment changes what the case brief contains.
      void queryClient.invalidateQueries({ queryKey: reviewKeys.run(caseId, runId), exact: true });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: key, exact: true });
      }
    },
  });
}
