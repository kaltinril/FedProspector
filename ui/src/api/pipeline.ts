import apiClient from './client';
import type {
  PipelineFunnelDto,
  PipelineCalendarEventDto,
  StaleProspectDto,
  RevenueForecastDto,
  ProspectMilestoneDto,
  CreateMilestoneRequest,
  UpdateMilestoneRequest,
  ReverseTimelineRequest,
  BulkStatusUpdateRequest,
  BulkStatusUpdateResult,
} from '@/types/pipeline';

export function getPipelineFunnel(): Promise<PipelineFunnelDto[]> {
  return apiClient.get('/pipeline/funnel').then((r) => r.data);
}

export function getPipelineCalendar(
  startDate: string,
  endDate: string,
): Promise<PipelineCalendarEventDto[]> {
  return apiClient
    .get('/pipeline/calendar', { params: { startDate, endDate } })
    .then((r) => r.data);
}

export function getStaleProspects(): Promise<StaleProspectDto[]> {
  return apiClient.get('/pipeline/stale').then((r) => r.data);
}

export function getRevenueForecast(): Promise<RevenueForecastDto[]> {
  return apiClient.get('/pipeline/forecast').then((r) => r.data);
}

export function getProspectMilestones(
  prospectId: number,
): Promise<ProspectMilestoneDto[]> {
  return apiClient.get(`/pipeline/prospects/${prospectId}/milestones`).then((r) => r.data);
}

export function createMilestone(
  prospectId: number,
  data: CreateMilestoneRequest,
): Promise<ProspectMilestoneDto> {
  return apiClient
    .post(`/pipeline/prospects/${prospectId}/milestones`, data)
    .then((r) => r.data);
}

export function updateMilestone(
  milestoneId: number,
  data: UpdateMilestoneRequest,
): Promise<ProspectMilestoneDto> {
  return apiClient.put(`/pipeline/milestones/${milestoneId}`, data).then((r) => r.data);
}

export function deleteMilestone(milestoneId: number): Promise<void> {
  return apiClient.delete(`/pipeline/milestones/${milestoneId}`).then(() => undefined);
}

export function generateTimeline(
  prospectId: number,
  data: ReverseTimelineRequest,
): Promise<ProspectMilestoneDto[]> {
  return apiClient
    .post(`/pipeline/prospects/${prospectId}/generate-timeline`, data)
    .then((r) => r.data);
}

export function bulkStatusUpdate(
  data: BulkStatusUpdateRequest,
): Promise<BulkStatusUpdateResult> {
  return apiClient.post('/pipeline/bulk-status', data).then((r) => r.data);
}
