import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchProposals,
  createProposal,
  updateProposal,
  getMilestones,
  createMilestone,
  updateMilestone,
  addDocument,
} from '@/api/proposals';
import type {
  ProposalSearchParams,
  CreateProposalRequest,
  UpdateProposalRequest,
  CreateMilestoneRequest,
  UpdateMilestoneRequest,
  AddProposalDocumentRequest,
} from '@/types/api';

export function useProposalSearch(params: ProposalSearchParams) {
  return useQuery({
    queryKey: queryKeys.proposals.list(params as Record<string, unknown>),
    queryFn: () => searchProposals(params),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useProposalMilestones(proposalId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.proposals.milestones(proposalId),
    queryFn: () => getMilestones(proposalId),
    staleTime: 2 * 60 * 1000,
    enabled,
  });
}

export function useCreateProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProposalRequest) => createProposal(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.proposals.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
    },
  });
}

export function useUpdateProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateProposalRequest }) =>
      updateProposal(id, data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.proposals.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
    },
  });
}

export function useCreateMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      proposalId,
      data,
    }: {
      proposalId: number;
      data: CreateMilestoneRequest;
    }) => createMilestone(proposalId, data),
    retry: 1,
    onSuccess: (_data, { proposalId }) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.proposals.milestones(proposalId),
      });
    },
  });
}

export function useUpdateMilestone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      proposalId,
      milestoneId,
      data,
    }: {
      proposalId: number;
      milestoneId: number;
      data: UpdateMilestoneRequest;
    }) => updateMilestone(proposalId, milestoneId, data),
    retry: 1,
    onSuccess: (_data, { proposalId }) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.proposals.milestones(proposalId),
      });
    },
  });
}

export function useAddDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      proposalId,
      data,
    }: {
      proposalId: number;
      data: AddProposalDocumentRequest;
    }) => addDocument(proposalId, data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.proposals.all });
    },
  });
}
