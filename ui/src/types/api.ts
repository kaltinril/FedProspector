// ============================================================
// Opportunity types (matching C# DTOs in Opportunities/)
// ============================================================

export interface OpportunitySearchResult {
  noticeId: string;
  title?: string | null;
  solicitationNumber?: string | null;
  departmentName?: string | null;
  office?: string | null;
  postedDate?: string | null;
  responseDeadline?: string | null;
  daysUntilDue?: number | null;
  setAsideCode?: string | null;
  setAsideDescription?: string | null;
  setAsideCategory?: string | null;
  naicsCode?: string | null;
  naicsDescription?: string | null;
  naicsSector?: string | null;
  sizeStandard?: string | null;
  baseAndAllOptions?: number | null;
  estimatedContractValue?: number | null;
  popState?: string | null;
  popCity?: string | null;
  prospectStatus?: string | null;
  assignedUser?: string | null;
}

export interface OpportunitySearchParams {
  setAside?: string;
  naics?: string;
  keyword?: string;
  solicitation?: string;
  daysOut?: number;
  openOnly?: boolean;
  department?: string;
  state?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface OpportunityDetail {
  noticeId: string;
  title?: string | null;
  solicitationNumber?: string | null;
  departmentName?: string | null;
  subTier?: string | null;
  office?: string | null;
  postedDate?: string | null;
  responseDeadline?: string | null;
  archiveDate?: string | null;
  type?: string | null;
  baseType?: string | null;
  setAsideCode?: string | null;
  setAsideDescription?: string | null;
  classificationCode?: string | null;
  naicsCode?: string | null;
  naicsDescription?: string | null;
  naicsSector?: string | null;
  sizeStandard?: string | null;
  setAsideCategory?: string | null;
  popState?: string | null;
  popZip?: string | null;
  popCountry?: string | null;
  popCity?: string | null;
  active?: string | null;
  awardNumber?: string | null;
  awardDate?: string | null;
  awardAmount?: number | null;
  awardeeUei?: string | null;
  awardeeName?: string | null;
  descriptionUrl?: string | null;
  descriptionText?: string | null;
  link?: string | null;
  resourceLinks?: string | null;
  resourceLinkDetails?: ResourceLinkDto[];
  estimatedContractValue?: number | null;
  securityClearanceRequired?: string | null;
  incumbentUei?: string | null;
  incumbentName?: string | null;
  periodOfPerformanceStart?: string | null;
  periodOfPerformanceEnd?: string | null;
  firstLoadedAt?: string | null;
  lastLoadedAt?: string | null;
  relatedAwards: RelatedAwardDto[];
  amendments?: AmendmentSummary[];
  prospect?: OpportunityProspectSummary | null;
  usaspendingAward?: UsaspendingSummaryDto | null;
}

export interface AmendmentSummary {
  noticeId: string;
  title?: string | null;
  type?: string | null;
  postedDate?: string | null;
  responseDeadline?: string | null;
  awardeeName: string | null;
  awardAmount: number | null;
}

export interface ResourceLinkDto {
  url: string;
  filename: string | null;
  contentType: string | null;
}

export interface RelatedAwardDto {
  contractId: string;
  vendorName?: string | null;
  vendorUei?: string | null;
  dateSigned?: string | null;
  dollarsObligated?: number | null;
  baseAndAllOptions?: number | null;
  typeOfContract?: string | null;
  numberOfOffers?: number | null;
}

export interface OpportunityProspectSummary {
  prospectId: number;
  source?: string | null;
  status: string;
  priority?: string | null;
  goNoGoScore?: number | null;
  winProbability?: number | null;
  assignedTo?: string | null;
}

export interface UsaspendingSummaryDto {
  generatedUniqueAwardId: string;
  recipientName?: string | null;
  recipientUei?: string | null;
  totalObligation?: number | null;
  baseAndAllOptionsValue?: number | null;
  startDate?: string | null;
  endDate?: string | null;
}

export interface TargetOpportunityDto {
  noticeId: string;
  title?: string | null;
  solicitationNumber?: string | null;
  departmentName?: string | null;
  office?: string | null;
  postedDate?: string | null;
  responseDeadline?: string | null;
  daysUntilDue?: number | null;
  setAsideCode?: string | null;
  setAsideDescription?: string | null;
  setAsideCategory?: string | null;
  naicsCode?: string | null;
  naicsDescription?: string | null;
  naicsLevel?: string | null;
  naicsSector?: string | null;
  sizeStandard?: string | null;
  sizeType?: string | null;
  awardAmount?: number | null;
  popState?: string | null;
  popCity?: string | null;
  descriptionUrl?: string | null;
  link?: string | null;
  prospectId?: number | null;
  prospectStatus?: string | null;
  prospectPriority?: string | null;
  assignedTo?: string | null;
}

export interface TargetSearchParams {
  minValue?: number;
  maxValue?: number;
  naicsSector?: string;
  setAside?: string;
  naics?: string;
  department?: string;
  state?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

// ============================================================
// Award types (matching C# DTOs in Awards/)
// ============================================================

export interface AwardSearchResult {
  contractId: string;
  solicitationNumber?: string | null;
  agencyName?: string | null;
  contractingOfficeName?: string | null;
  vendorName?: string | null;
  vendorUei?: string | null;
  dateSigned?: string | null;
  effectiveDate?: string | null;
  completionDate?: string | null;
  dollarsObligated?: number | null;
  baseAndAllOptions?: number | null;
  naicsCode?: string | null;
  pscCode?: string | null;
  setAsideType?: string | null;
  typeOfContract?: string | null;
  numberOfOffers?: number | null;
  extentCompeted?: string | null;
  description?: string | null;
  dataSource?: 'fpds' | 'usaspending' | null;
}

export interface AwardSearchParams {
  solicitation?: string;
  naics?: string;
  agency?: string;
  vendorUei?: string;
  vendorName?: string;
  setAside?: string;
  minValue?: number;
  maxValue?: number;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface AwardDetail {
  contractId: string;
  idvPiid?: string | null;
  agencyId?: string | null;
  agencyName?: string | null;
  contractingOfficeId?: string | null;
  contractingOfficeName?: string | null;
  fundingAgencyId?: string | null;
  fundingAgencyName?: string | null;
  vendorUei?: string | null;
  vendorName?: string | null;
  dateSigned?: string | null;
  effectiveDate?: string | null;
  completionDate?: string | null;
  ultimateCompletionDate?: string | null;
  lastModifiedDate?: string | null;
  dollarsObligated?: number | null;
  baseAndAllOptions?: number | null;
  naicsCode?: string | null;
  pscCode?: string | null;
  setAsideType?: string | null;
  typeOfContract?: string | null;
  typeOfContractPricing?: string | null;
  description?: string | null;
  popState?: string | null;
  popCountry?: string | null;
  popZip?: string | null;
  extentCompeted?: string | null;
  numberOfOffers?: number | null;
  solicitationNumber?: string | null;
  solicitationDate?: string | null;
  transactions: TransactionDto[];
  vendorProfile?: VendorSummaryDto | null;
}

export interface AwardDetailResponse {
  contractId: string;
  dataStatus: 'full' | 'partial' | 'not_loaded';
  hasFpdsData: boolean;
  hasUsaspendingData: boolean;
  detail?: AwardDetail | null;
  loadStatus?: LoadRequestStatus | null;
}

export interface LoadRequestStatus {
  requestId?: number | null;
  requestType?: string | null;
  status?: string | null;
  requestedAt?: string | null;
  errorMessage?: string | null;
}

export interface RequestLoadDto {
  tier: 'usaspending' | 'fpds';
}

export interface TransactionDto {
  actionDate: string;
  modificationNumber?: string | null;
  actionType?: string | null;
  actionTypeDescription?: string | null;
  federalActionObligation?: number | null;
  description?: string | null;
}

export interface VendorSummaryDto {
  ueiSam: string;
  legalBusinessName?: string | null;
  dbaName?: string | null;
  registrationStatus?: string | null;
  primaryNaics?: string | null;
  entityUrl?: string | null;
}

export interface BurnRateDto {
  contractId: string;
  totalObligated: number;
  baseAndAllOptions?: number | null;
  percentSpent?: number | null;
  monthsElapsed: number;
  monthlyRate: number;
  transactionCount: number;
  monthlyBreakdown: MonthlySpendDto[];
}

export interface MonthlySpendDto {
  yearMonth: string;
  amount: number;
  transactionCount: number;
}

export interface MarketShareDto {
  vendorName: string;
  vendorUei: string;
  awardCount: number;
  totalValue: number;
  averageValue: number;
  lastAwardDate: string | null;
}

// ============================================================
// Entity types (matching C# DTOs in Entities/)
// ============================================================

export interface EntitySearchResult {
  ueiSam: string;
  legalBusinessName: string;
  dbaName?: string | null;
  registrationStatus?: string | null;
  primaryNaics?: string | null;
  entityStructureCode?: string | null;
  popState?: string | null;
  entityUrl?: string | null;
  lastUpdateDate?: string | null;
  registrationExpirationDate?: string | null;
}

export interface EntitySearchParams {
  name?: string;
  uei?: string;
  naics?: string;
  state?: string;
  businessType?: string;
  sbaCertification?: string;
  registrationStatus?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface EntityDetail {
  ueiSam: string;
  ueiDuns?: string | null;
  cageCode?: string | null;
  legalBusinessName: string;
  dbaName?: string | null;
  registrationStatus?: string | null;
  initialRegistrationDate?: string | null;
  registrationExpirationDate?: string | null;
  lastUpdateDate?: string | null;
  activationDate?: string | null;
  entityStructureCode?: string | null;
  primaryNaics?: string | null;
  entityUrl?: string | null;
  stateOfIncorporation?: string | null;
  countryOfIncorporation?: string | null;
  exclusionStatusFlag?: string | null;
  addresses: EntityAddressDto[];
  naicsCodes: EntityNaicsDto[];
  pscCodes: EntityPscDto[];
  businessTypes: EntityBusinessTypeDto[];
  sbaCertifications: EntitySbaCertificationDto[];
  pointsOfContact: EntityPocDto[];
}

export interface EntityAddressDto {
  addressType: string;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  stateOrProvince?: string | null;
  zipCode?: string | null;
  countryCode?: string | null;
  congressionalDistrict?: string | null;
}

export interface EntityNaicsDto {
  naicsCode: string;
  isPrimary?: string | null;
  sbaSmallBusiness?: string | null;
}

export interface EntityPscDto {
  pscCode: string;
}

export interface EntityBusinessTypeDto {
  businessTypeCode: string;
}

export interface EntitySbaCertificationDto {
  sbaTypeCode?: string | null;
  sbaTypeDesc?: string | null;
  certificationEntryDate?: string | null;
  certificationExitDate?: string | null;
}

export interface EntityPocDto {
  pocType: string;
  firstName?: string | null;
  middleInitial?: string | null;
  lastName?: string | null;
  title?: string | null;
  city?: string | null;
  stateOrProvince?: string | null;
  countryCode?: string | null;
}

export interface CompetitorProfileDto {
  ueiSam: string;
  legalBusinessName?: string | null;
  primaryNaics?: string | null;
  naicsDescription?: string | null;
  naicsSector?: string | null;
  entityStructure?: string | null;
  businessTypes?: string | null;
  businessTypeCategories?: string | null;
  sbaCertifications?: string | null;
  pastContracts: number;
  totalObligated?: number | null;
  mostRecentAward?: string | null;
  winRate?: number | null;
  averageContractSize?: number | null;
  recentAwards: RecentAwardDto[];
}

export interface RecentAwardDto {
  contractId?: string | null;
  vendorName?: string | null;
  dateSigned?: string | null;
  dollarsObligated?: number | null;
}

export interface ExclusionCheckDto {
  uei: string;
  entityName?: string | null;
  isExcluded: boolean;
  activeExclusions: ExclusionDto[];
  checkedAt: string;
}

export interface ExclusionDto {
  exclusionType?: string | null;
  exclusionProgram?: string | null;
  excludingAgencyName?: string | null;
  activationDate?: string | null;
  terminationDate?: string | null;
  additionalComments?: string | null;
}

// ============================================================
// Subaward types (matching C# DTOs in Subawards/)
// ============================================================

export interface SubawardDetailDto {
  subName?: string | null;
  subUei?: string | null;
  subAmount?: number | null;
  subDate?: string | null;
  subDescription?: string | null;
  naicsCode?: string | null;
}

export interface TeamingPartnerDto {
  primeUei?: string | null;
  primeName?: string | null;
  subCount: number;
  totalSubAmount?: number | null;
  uniqueSubs: number;
  naicsCodes?: string | null;
}

export interface TeamingPartnerSearchParams {
  naics?: string;
  minSubawards?: number;
  primeUei?: string;
  subUei?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

// ============================================================
// Prospect types (matching C# DTOs in Prospects/)
// ============================================================

export interface ProspectListDto {
  prospectId: number;
  noticeId: string;
  source?: string | null;
  status: string;
  priority?: string | null;
  goNoGoScore?: number | null;
  estimatedValue?: number | null;
  assignedToName?: string | null;
  captureManagerName?: string | null;
  opportunityTitle?: string | null;
  responseDeadline?: string | null;
  setAsideCode?: string | null;
  naicsCode?: string | null;
  departmentName?: string | null;
  active?: string | null;
  createdAt?: string | null;
}

export interface ProspectSearchParams {
  status?: string;
  source?: string;
  assignedTo?: number;
  captureManagerId?: number;
  priority?: string;
  naics?: string;
  setAside?: string;
  openOnly?: boolean;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface ProspectDetailDto {
  prospect: ProspectSummaryDto;
  opportunity?: ProspectOpportunityDto | null;
  notes: ProspectNoteDto[];
  teamMembers: ProspectTeamMemberDto[];
  proposal?: ProspectProposalSummaryDto | null;
  scoreBreakdown?: ScoreBreakdownDto | null;
}

export interface ProspectSummaryDto {
  prospectId: number;
  noticeId: string;
  source?: string | null;
  status: string;
  priority?: string | null;
  goNoGoScore?: number | null;
  winProbability?: number | null;
  estimatedValue?: number | null;
  estimatedGrossMarginPct?: number | null;
  bidSubmittedDate?: string | null;
  outcome?: string | null;
  outcomeDate?: string | null;
  outcomeNotes?: string | null;
  captureManager?: UserSummaryDto | null;
  assignedTo?: UserSummaryDto | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface UserSummaryDto {
  userId: number;
  displayName: string;
}

export interface ProspectOpportunityDto {
  title?: string | null;
  solicitationNumber?: string | null;
  departmentName?: string | null;
  subTier?: string | null;
  office?: string | null;
  postedDate?: string | null;
  responseDeadline?: string | null;
  type?: string | null;
  setAsideCode?: string | null;
  setAsideDescription?: string | null;
  naicsCode?: string | null;
  popState?: string | null;
  popZip?: string | null;
  popCountry?: string | null;
  active?: string | null;
  awardAmount?: number | null;
  link?: string | null;
}

export interface ProspectNoteDto {
  noteId: number;
  noteType?: string | null;
  noteText: string;
  createdBy?: UserSummaryDto | null;
  createdAt?: string | null;
}

export interface ProspectTeamMemberDto {
  id: number;
  ueiSam?: string | null;
  entityName?: string | null;
  role?: string | null;
  notes?: string | null;
  proposedHourlyRate?: number | null;
  commitmentPct?: number | null;
}

export interface ProspectProposalSummaryDto {
  proposalId: number;
  proposalStatus: string;
  submissionDeadline?: string | null;
  submittedAt?: string | null;
  estimatedValue?: number | null;
}

export interface ScoreBreakdownDto {
  prospectId: number;
  totalScore: number;
  maxScore: number;
  percentage: number;
  breakdown: ScoreCriteriaBreakdownDto;
}

export interface ScoreCriteriaBreakdownDto {
  setAside: ScoreCriterionDto;
  timeRemaining: ScoreCriterionDto;
  naicsMatch: ScoreCriterionDto;
  awardValue: ScoreCriterionDto;
}

export interface ScoreCriterionDto {
  score: number;
  max: number;
  detail: string;
}

export interface CreateProspectRequest {
  noticeId?: string | null;
  assignedTo?: number | null;
  captureManagerId?: number | null;
  priority?: string | null;
  notes?: string | null;
}

export interface UpdateProspectStatusRequest {
  newStatus?: string | null;
  notes?: string | null;
}

export interface ReassignProspectRequest {
  newAssignedTo: number;
  notes?: string | null;
}

export interface CreateProspectNoteRequest {
  noteType?: string | null;
  noteText?: string | null;
}

export interface AddTeamMemberRequest {
  ueiSam?: string | null;
  role?: string | null;
  notes?: string | null;
  proposedHourlyRate?: number | null;
  commitmentPct?: number | null;
}

// ============================================================
// Proposal types (matching C# DTOs in Proposals/)
// ============================================================

export interface ProposalDetailDto {
  proposalId: number;
  prospectId: number;
  proposalNumber?: string | null;
  prospectTitle?: string | null;
  opportunityTitle?: string | null;
  proposalStatus: string;
  submissionDeadline?: string | null;
  submittedAt?: string | null;
  estimatedValue?: number | null;
  winProbabilityPct?: number | null;
  lessonsLearned?: string | null;
  milestones: ProposalMilestoneDto[];
  documents: ProposalDocumentDto[];
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ProposalSearchParams {
  status?: string;
  prospectId?: number;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface ProposalMilestoneDto {
  milestoneId: number;
  milestoneName: string;
  dueDate?: string | null;
  completedDate?: string | null;
  assignedTo?: number | null;
  status: string;
  notes?: string | null;
  createdAt?: string | null;
}

export interface ProposalDocumentDto {
  documentId: number;
  documentType: string;
  fileName: string;
  fileSizeBytes?: number | null;
  uploadedBy?: number | null;
  uploadedAt?: string | null;
  notes?: string | null;
}

export interface CreateProposalRequest {
  prospectId: number;
  submissionDeadline?: string | null;
  estimatedValue?: number | null;
}

export interface UpdateProposalRequest {
  status?: string | null;
  estimatedValue?: number | null;
  winProbabilityPct?: number | null;
  lessonsLearned?: string | null;
}

export interface CreateMilestoneRequest {
  title?: string | null;
  dueDate: string;
  assignedTo?: number | null;
}

export interface UpdateMilestoneRequest {
  completedDate?: string | null;
  status?: string | null;
  notes?: string | null;
}

export interface AddProposalDocumentRequest {
  fileName?: string | null;
  documentType?: string | null;
  fileSizeBytes?: number | null;
  notes?: string | null;
}

// ============================================================
// Dashboard types (matching C# DTOs in Dashboard/)
// ============================================================

export interface DashboardDto {
  prospectsByStatus: StatusCountDto[];
  dueThisWeek: DueOpportunityDto[];
  workloadByAssignee: AssigneeWorkloadDto[];
  winLossMetrics: OutcomeCountDto[];
  recentSavedSearches: SavedSearchSummaryDto[];
  totalOpenProspects: number;
  pipelineValue: number;
  autoMatchCount: number;
}

export interface StatusCountDto {
  status: string;
  count: number;
}

export interface DueOpportunityDto {
  prospectId: number;
  status?: string | null;
  priority?: string | null;
  title?: string | null;
  responseDeadline?: string | null;
  setAsideCode?: string | null;
  assignedTo?: string | null;
}

export interface AssigneeWorkloadDto {
  username: string;
  displayName?: string | null;
  count: number;
}

export interface OutcomeCountDto {
  outcome: string;
  count: number;
}

export interface SavedSearchSummaryDto {
  searchId: number;
  searchName: string;
  username?: string | null;
  lastRunAt?: string | null;
  lastNewResults?: number | null;
}

// ============================================================
// SavedSearch types (matching C# DTOs in SavedSearches/)
// ============================================================

export interface SavedSearchDto {
  searchId: number;
  searchName: string;
  description?: string | null;
  filterCriteria: string;
  notificationEnabled?: string | null;
  isActive?: string | null;
  lastRunAt?: string | null;
  lastNewResults?: number | null;
  createdAt?: string | null;
}

export interface SavedSearchFilterCriteria {
  setAsideCodes?: string[] | null;
  naicsCodes?: string[] | null;
  states?: string[] | null;
  minAwardAmount?: number | null;
  maxAwardAmount?: number | null;
  openOnly?: boolean;
  types?: string[] | null;
  daysBack?: number | null;
}

export interface CreateSavedSearchRequest {
  searchName?: string | null;
  description?: string | null;
  filterCriteria?: SavedSearchFilterCriteria;
  notificationEnabled?: boolean;
}

export interface UpdateSavedSearchRequest {
  name?: string | null;
  description?: string | null;
  filterCriteria?: SavedSearchFilterCriteria;
  notificationsEnabled?: boolean | null;
}

export interface SavedSearchRunResultDto {
  searchId: number;
  searchName: string;
  results: OpportunitySearchResult[];
  totalCount: number;
  newCount: number;
  executedAt: string;
}

// ============================================================
// Notification types (matching C# DTOs in Notifications/)
// ============================================================

export interface NotificationDto {
  notificationId: number;
  notificationType: string;
  title: string;
  message?: string | null;
  entityType?: string | null;
  entityId?: string | null;
  isRead: boolean;
  createdAt?: string | null;
  readAt?: string | null;
}

export interface NotificationListParams {
  unreadOnly?: boolean;
  type?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

export interface NotificationListResponse {
  notifications: import('./common').PagedResponse<NotificationDto>;
  unreadCount: number;
}

// ============================================================
// Admin types (matching C# DTOs in Admin/)
// ============================================================

export interface EtlStatusDto {
  sources: EtlSourceStatusDto[];
  apiUsage: ApiUsageDto[];
  recentErrors: RecentErrorDto[];
  alerts: string[];
}

export interface EtlSourceStatusDto {
  sourceSystem: string;
  label: string;
  lastLoadAt?: string | null;
  hoursSinceLoad?: number | null;
  thresholdHours: number;
  status: string;
  recordsProcessed: number;
}

export interface ApiUsageDto {
  sourceSystem: string;
  requestsMade: number;
  maxRequests: number;
  remaining: number;
  lastRequestAt?: string | null;
}

export interface RecentErrorDto {
  sourceSystem: string;
  loadType?: string | null;
  startedAt: string;
  errorMessage?: string | null;
}

export interface UserListDto {
  userId: number;
  username: string;
  displayName: string;
  email?: string | null;
  role: string;
  isActive: boolean;
  isOrgAdmin: boolean;
  lastLoginAt?: string | null;
  createdAt?: string | null;
}

export interface UpdateUserRequest {
  role?: string | null;
  isOrgAdmin?: boolean | null;
  isActive?: boolean | null;
}

export interface ResetPasswordResponse {
  message: string;
  temporaryPassword: string;
}

export interface CreateOrganizationRequest {
  name: string;
  slug: string;
}

export interface CreateOwnerRequest {
  email: string;
  password: string;
  displayName: string;
}

// ============================================================
// Intelligence types (Phase 45)
// ============================================================

export interface PWinFactorDto {
  name: string;
  score: number;
  weight: number;
  weightedScore: number;
  detail: string;
}

export interface PWinResultDto {
  prospectId: number | null;
  noticeId: string;
  score: number;
  category: string;  // "High" | "Medium" | "Low" | "VeryLow"
  factors: PWinFactorDto[];
  suggestions: string[];
}

export interface QualificationItemDto {
  name: string;
  category: string;  // "Certification" | "Experience" | "Compliance" | "Logistics"
  status: string;    // "Pass" | "Fail" | "Warning" | "Unknown"
  detail: string;
  sourceUei?: string | null;
}

export interface QualificationCheckDto {
  noticeId: string;
  passCount: number;
  failCount: number;
  warningCount: number;
  totalChecks: number;
  overallStatus: string;  // "Qualified" | "Partially Qualified" | "Not Qualified"
  checks: QualificationItemDto[];
}

export interface IncumbentAnalysisDto {
  noticeId: string;
  hasIncumbent: boolean;
  incumbentUei: string | null;
  incumbentName: string | null;
  contractId: string | null;
  contractValue: number | null;
  dollarsObligated: number | null;
  periodStart: string | null;
  periodEnd: string | null;
  monthsRemaining: number | null;
  monthlyBurnRate: number | null;
  percentSpent: number | null;
  registrationStatus: string | null;
  registrationExpiration: string | null;
  isExcluded: boolean;
  exclusionType: string | null;
  totalContractsInNaics: number;
  consecutiveWins: number;
  vulnerabilitySignals: string[];
  isLikelyIncumbent: boolean;
  likelyCompetitors: LikelyCompetitorDto[];
}

export interface LikelyCompetitorDto {
  vendorName: string;
  ueiSam: string | null;
  contractCount: number;
  totalValue: number;
}

export interface CompetitiveLandscapeDto {
  naicsCode: string;
  agencyCode: string;
  setAsideCode: string | null;
  totalContracts: number;
  totalValue: number;
  averageAwardValue: number;
  agencyAverageAwardValue: number;
  topVendors: VendorShareDto[];
  competitionLevel: string;
  distinctVendorCount: number;
  fallbackScope: string | null;
}

export interface VendorShareDto {
  vendorUei: string | null;
  vendorName: string | null;
  contractCount: number;
  totalValue: number;
  marketSharePercent: number;
}

export interface IntelMarketShareDto {
  naicsCode: string;
  naicsDescription: string | null;
  yearsAnalyzed: number;
  totalContracts: number;
  totalValue: number;
  averageAwardValue: number;
  topVendors: VendorShareDto[];
}

export interface RecommendedOpportunityDto {
  noticeId: string;
  title: string | null;
  solicitationNumber: string | null;
  departmentName: string | null;
  subTier: string | null;
  setAsideCode: string | null;
  setAsideDescription: string | null;
  naicsCode: string | null;
  naicsDescription: string | null;
  classificationCode: string | null;
  noticeType: string | null;
  awardAmount: number | null;
  postedDate: string | null;
  responseDeadline: string | null;
  daysRemaining: number | null;
  popState: string | null;
  popCity: string | null;
  popCountry: string | null;
  qScore: number;
  qScoreCategory: string;
  qScoreFactors: QScoreFactorDto[];
  isRecompete: boolean;
  incumbentName: string | null;
}

export interface QScoreFactorDto {
  name: string;
  points: number;
  maxPoints: number;
}

export interface ExpiringContractDto {
  piid: string;
  description: string | null;
  naicsCode: string | null;
  setAsideType: string | null;
  vendorUei: string | null;
  vendorName: string | null;
  agencyName: string | null;
  officeName: string | null;
  contractValue: number | null;
  dollarsObligated: number | null;
  completionDate: string | null;
  dateSigned: string | null;
  monthsRemaining: number | null;
  registrationStatus: string | null;
  registrationExpiration: string | null;
  isExcluded: boolean;
  exclusionType: string | null;
  monthlyBurnRate: number | null;
  percentSpent: number | null;
  resolicitationNoticeId: string | null;
  resolicitationStatus: string;
  predecessorSetAsideType: string | null;
  shiftDetected: boolean | null;
}

// ============================================================
// Admin Load History types (Phase 70)
// ============================================================

export interface LoadHistoryDto {
  loadId: number;
  sourceSystem: string;
  loadType: string;
  status: string;
  startedAt: string;
  completedAt?: string | null;
  durationSeconds?: number | null;
  recordsRead: number;
  recordsInserted: number;
  recordsUpdated: number;
  recordsErrored: number;
  errorMessage?: string | null;
}

export interface LoadHistoryResponse {
  items: LoadHistoryDto[];
  page: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
}

export interface LoadHistoryParams {
  source?: string;
  status?: string;
  days?: number;
  page?: number;
  pageSize?: number;
}

export interface HealthResponse {
  status: string;
  database: HealthComponentDto;
  etlFreshness: HealthComponentDto;
  details?: Record<string, string>;
}

export interface HealthComponentDto {
  status: string;
  description?: string | null;
  data?: Record<string, string | number | boolean | null>;
}

// ============================================================
// Batch pWin types (Phase 104B)
// ============================================================

export interface BatchPWinRequest {
  noticeIds: string[];
}

export interface BatchPWinEntry {
  score: number;
  category: string;
}

export interface BatchPWinResponse {
  results: Record<string, BatchPWinEntry | null>;
}

// ============================================================
// Set-Aside Shift types (Phase 109)
// ============================================================

export interface SetAsideShiftDto {
  noticeId: string;
  solicitationNumber: string | null;
  currentSetAsideCode: string | null;
  currentSetAsideDescription: string | null;
  predecessorSetAsideType: string | null;
  predecessorVendorName: string | null;
  predecessorVendorUei: string | null;
  predecessorDateSigned: string | null;
  predecessorValue: number | null;
  shiftDetected: boolean | null;
}

export interface SetAsideTrendDto {
  naicsCode: string;
  fiscalYear: number;
  setAsideType: string | null;
  setAsideCategory: string | null;
  contractCount: number;
  totalValue: number;
  avgValue: number;
}

// ============================================================
// Document Intelligence types (Phase 110)
// ============================================================

export interface DocumentIntelligenceDto {
  noticeId: string;
  attachmentCount: number;
  analyzedCount: number;
  latestExtractionMethod?: string;
  availableMethods: string[];
  lastExtractedAt?: string;
  clearanceRequired?: string;
  clearanceLevel?: string;
  clearanceScope?: string;
  evalMethod?: string;
  vehicleType?: string;
  isRecompete?: string;
  incumbentName?: string;
  scopeSummary?: string;
  periodOfPerformance?: string;
  laborCategories: string[];
  keyRequirements: string[];
  overallConfidence: string;
  confidenceDetails?: Record<string, string>;
  clearanceDetails?: string;
  evalDetails?: string;
  vehicleDetails?: string;
  recompeteDetails?: string;
  pricingDetails?: string;
  popDetails?: string;
  sources: IntelSourceDto[];
  mergedPassages: MergedSourcePassageDto[];
  attachments: AttachmentSummaryDto[];
  perAttachmentIntel?: AttachmentIntelBreakdownDto[];
}

export interface IntelSourceDto {
  fieldName: string;
  sourceFilename?: string;
  pageNumber?: number;
  matchedText?: string;
  surroundingContext?: string;
  charOffsetStart?: number;
  charOffsetEnd?: number;
  extractionMethod: string;
  confidence: string;
}

export interface AttachmentSummaryDto {
  attachmentId: number;
  filename: string;
  contentType?: string;
  fileSizeBytes?: number;
  pageCount?: number;
  downloadStatus: string;
  extractionStatus: string;
  skipReason?: string;
  url?: string;
  resourceGuid?: string;
}

export interface AttachmentIntelBreakdownDto {
  attachmentId: number;
  filename: string;
  extractionMethod: string;
  confidence?: string;
  clearanceRequired?: string;
  clearanceLevel?: string;
  evalMethod?: string;
  vehicleType?: string;
  isRecompete?: string;
  incumbentName?: string;
  pricingStructure?: string;
  placeOfPerformance?: string;
}

export interface MergedSourcePassageDto {
  fieldName: string;
  filename: string;
  pageNumber?: number;
  methods: string[];
  confidences: string[];
  text: string;
  highlights: HighlightSpan[];
  matchCount: number;
}

export interface HighlightSpan {
  start: number;
  end: number;
  matchedText: string;
}

export interface LoadRequestStatusDto {
  requestId?: number | null;
  requestType?: string | null;
  status?: string | null;
  requestedAt?: string | null;
  errorMessage?: string | null;
}

export interface AnalysisEstimateDto {
  noticeId: string;
  attachmentCount: number;
  totalChars: number;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  estimatedCostUsd: number;
  model: string;
  alreadyAnalyzed: number;
  remainingToAnalyze: number;
}

export interface FetchDescriptionResponse {
  noticeId: string;
  descriptionText: string;
}
