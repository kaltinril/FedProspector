// ============================================================
// Pipeline & Workflow types (matching C# DTOs in Pipeline/)
// ============================================================

export interface PipelineFunnelDto {
  status: string;
  prospectCount: number;
  totalEstimatedValue?: number | null;
  avgHoursInPriorStatus?: number | null;
  winRatePct?: number | null;
  wonCount?: number | null;
  lostCount?: number | null;
}

export interface PipelineCalendarEventDto {
  prospectId: number;
  noticeId: string;
  opportunityTitle?: string | null;
  responseDeadline?: string | null;
  solicitationNumber?: string | null;
  status: string;
  priority?: string | null;
  assignedTo?: number | null;
  assignedToName?: string | null;
  estimatedValue?: number | null;
  winProbability?: number | null;
}

export interface StaleProspectDto {
  prospectId: number;
  noticeId: string;
  opportunityTitle?: string | null;
  status: string;
  priority?: string | null;
  daysSinceUpdate: number;
  assignedTo?: number | null;
  assignedToName?: string | null;
  estimatedValue?: number | null;
  lastUpdatedAt: string;
}

export interface RevenueForecastDto {
  forecastMonth: string;
  prospectCount: number;
  totalUnweightedValue?: number | null;
  totalWeightedValue?: number | null;
  avgWinProbability?: number | null;
}

export interface ProspectMilestoneDto {
  prospectMilestoneId: number;
  prospectId: number;
  milestoneName: string;
  targetDate: string;
  completedDate?: string | null;
  isCompleted: boolean;
  sortOrder: number;
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreateMilestoneRequest {
  milestoneName: string;
  targetDate: string;
  sortOrder?: number;
  notes?: string;
}

export interface UpdateMilestoneRequest {
  milestoneName?: string;
  targetDate?: string;
  completedDate?: string | null;
  isCompleted?: boolean;
  sortOrder?: number;
  notes?: string | null;
}

export interface ReverseTimelineRequest {
  responseDeadline: string;
  templateName?: string | null;
  customMilestones?: TimelineMilestoneDefinition[] | null;
}

export interface TimelineMilestoneDefinition {
  milestoneName: string;
  daysBeforeDeadline: number;
}

export interface BulkStatusUpdateRequest {
  prospectIds: number[];
  newStatus: string;
  notes?: string;
}

export interface BulkStatusUpdateResult {
  updated: number;
  skipped: number;
  errors?: string[];
}
