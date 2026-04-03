import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getPipelineFunnel,
  getPipelineCalendar,
  getStaleProspects,
  getRevenueForecast,
  getProspectMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
  generateTimeline,
  bulkStatusUpdate,
} from '@/api/pipeline';
import type {
  CreateMilestoneRequest,
  UpdateMilestoneRequest,
  ReverseTimelineRequest,
  BulkStatusUpdateRequest,
} from '@/types/pipeline';

export function usePipelineFunnel() {
  return useQuery({
    queryKey: queryKeys.pipeline.funnel,
    queryFn: () => getPipelineFunnel(),
    staleTime: 60 * 1000,
  });
}

export function usePipelineCalendar(startDate: string, endDate: string) {
  return useQuery({
    queryKey: queryKeys.pipeline.calendar(startDate, endDate),
    queryFn: () => getPipelineCalendar(startDate, endDate),
    staleTime: 60 * 1000,
    enabled: !!startDate && !!endDate,
  });
}

export function useStaleProspects() {
  return useQuery({
    queryKey: queryKeys.pipeline.stale,
    queryFn: () => getStaleProspects(),
    staleTime: 60 * 1000,
  });
}

export function useRevenueForecast() {
  return useQuery({
    queryKey: queryKeys.pipeline.forecast,
    queryFn: () => getRevenueForecast(),
    staleTime: 60 * 1000,
  });
}

export function useProspectMilestones(prospectId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.pipeline.milestones(prospectId),
    queryFn: () => getProspectMilestones(prospectId),
    staleTime: 60 * 1000,
    enabled: enabled && prospectId > 0,
  });
}

export function useCreateMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ prospectId, data }: { prospectId: number; data: CreateMilestoneRequest }) =>
      createMilestone(prospectId, data),
    retry: 1,
    onSuccess: (_data, { prospectId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.milestones(prospectId) });
    },
  });
}

export function useUpdateMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      milestoneId,
      data,
    }: {
      milestoneId: number;
      prospectId: number;
      data: UpdateMilestoneRequest;
    }) => updateMilestone(milestoneId, data),
    retry: 1,
    onSuccess: (_data, { prospectId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.milestones(prospectId) });
    },
  });
}

export function useDeleteMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      milestoneId,
    }: {
      milestoneId: number;
      prospectId: number;
    }) => deleteMilestone(milestoneId),
    retry: 1,
    onSuccess: (_data, { prospectId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.milestones(prospectId) });
    },
  });
}

export function useGenerateTimeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      prospectId,
      data,
    }: {
      prospectId: number;
      data: ReverseTimelineRequest;
    }) => generateTimeline(prospectId, data),
    retry: 1,
    onSuccess: (_data, { prospectId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.milestones(prospectId) });
    },
  });
}

export function useBulkStatusUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BulkStatusUpdateRequest) => bulkStatusUpdate(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}
