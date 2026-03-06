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
  link?: string | null;
  resourceLinks?: string | null;
  estimatedContractValue?: number | null;
  securityClearanceRequired?: string | null;
  incumbentUei?: string | null;
  incumbentName?: string | null;
  periodOfPerformanceStart?: string | null;
  periodOfPerformanceEnd?: string | null;
  firstLoadedAt?: string | null;
  lastLoadedAt?: string | null;
  relatedAwards: RelatedAwardDto[];
  prospect?: OpportunityProspectSummary | null;
  usaspendingAward?: UsaspendingSummaryDto | null;
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
  isAdmin: boolean;
  lastLoginAt?: string | null;
  createdAt?: string | null;
}

export interface UpdateUserRequest {
  role?: string | null;
  isAdmin?: boolean | null;
  isActive?: boolean | null;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface CreateOrganizationRequest {
  name?: string | null;
  slug?: string | null;
}

export interface CreateOwnerRequest {
  email?: string | null;
  password?: string | null;
  displayName?: string | null;
}
