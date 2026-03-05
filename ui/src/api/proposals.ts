import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  ProposalDetailDto,
  ProposalSearchParams,
  ProposalMilestoneDto,
  ProposalDocumentDto,
  CreateProposalRequest,
  UpdateProposalRequest,
  CreateMilestoneRequest,
  UpdateMilestoneRequest,
  AddProposalDocumentRequest,
} from '@/types/api';

export function searchProposals(
  params: ProposalSearchParams,
): Promise<PagedResponse<ProposalDetailDto>> {
  return apiClient.get('/proposals', { params }).then((r) => r.data);
}

export function createProposal(data: CreateProposalRequest): Promise<ProposalDetailDto> {
  return apiClient.post('/proposals', data).then((r) => r.data);
}

export function updateProposal(
  id: number,
  data: UpdateProposalRequest,
): Promise<ProposalDetailDto> {
  return apiClient.patch(`/proposals/${id}`, data).then((r) => r.data);
}

export function getMilestones(proposalId: number): Promise<ProposalMilestoneDto[]> {
  return apiClient.get(`/proposals/${proposalId}/milestones`).then((r) => r.data);
}

export function createMilestone(
  proposalId: number,
  data: CreateMilestoneRequest,
): Promise<ProposalMilestoneDto> {
  return apiClient.post(`/proposals/${proposalId}/milestones`, data).then((r) => r.data);
}

export function updateMilestone(
  proposalId: number,
  milestoneId: number,
  data: UpdateMilestoneRequest,
): Promise<ProposalMilestoneDto> {
  return apiClient
    .patch(`/proposals/${proposalId}/milestones/${milestoneId}`, data)
    .then((r) => r.data);
}

export function addDocument(
  proposalId: number,
  data: AddProposalDocumentRequest,
): Promise<ProposalDocumentDto> {
  return apiClient.post(`/proposals/${proposalId}/documents`, data).then((r) => r.data);
}
